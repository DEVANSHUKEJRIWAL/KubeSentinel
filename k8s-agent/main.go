package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/client-go/util/homedir"
)

// If you ever get Slack, paste the URL here. For now, we use "MOCK".
const SLACK_WEBHOOK_URL = "MOCK"

const (
	hpaName           = "victim-app-hpa"
	namespace         = "default"
	pollInterval      = 5 * time.Second
	stabilizationWin  = 60 * time.Second // relax minReplicas only after this quiet period
	minActionInterval = 15 * time.Second // rate-limit: min gap between HPA patches
	floorMinReplicas  = int32(1)         // guardrail: never scale to zero
)

type Interval struct {
	Lower float64 `json:"lower"`
	Upper float64 `json:"upper"`
}

type PredictionResponse struct {
	CurrentCPU          float64  `json:"current_cpu"`
	PredictedCPU        float64  `json:"predicted_cpu"`
	Interval            Interval `json:"interval"`
	RecommendedReplicas int32    `json:"recommended_replicas"`
	Action              string   `json:"action"`
	Status              string   `json:"status"`
}

type SlackMessage struct {
	Text string `json:"text"`
}

func main() {
	fmt.Println("🤖 Sentinel Agent starting (predictive HPA mode)...")
	clientset := mustConnect()
	fmt.Println("✅ Connected to Kubernetes cluster!")

	// Rate-limit / anti-flapping state.
	var lastPatch, lastScaleUp time.Time

	for {
		time.Sleep(pollInterval)

		pred, ok := fetchPrediction()
		if !ok {
			continue
		}
		if pred.Status == "warning" {
			fmt.Println("⏳ Waiting for data...")
			continue
		}

		fmt.Printf("🧠 cpu=%.4f pred=%.4f upper=%.4f rec=%d action=%s\n",
			pred.CurrentCPU, pred.PredictedCPU, pred.Interval.Upper, pred.RecommendedReplicas, pred.Action)

		now := time.Now()
		switch pred.Action {
		case "scale_up":
			lastScaleUp = now
			// Raise the floor ahead of the predicted peak so pods are ready
			// BEFORE load arrives, rather than reacting after CPU climbs.
			if now.Sub(lastPatch) < minActionInterval {
				continue // rate-limited
			}
			if setMinReplicas(clientset, pred.RecommendedReplicas) {
				lastPatch = now
				sendSlackAlert(fmt.Sprintf(
					"🚨 *Sentinel Ops* 🚨\nForecast spike (upper %.3f cores) → raising `%s` minReplicas toward %d *before* the peak.",
					pred.Interval.Upper, hpaName, pred.RecommendedReplicas))
			}
		default: // "maintain"
			// Only relax the floor once it's been quiet for the stabilization
			// window, so a brief dip doesn't scale us back down into the spike.
			if now.Sub(lastScaleUp) > stabilizationWin && now.Sub(lastPatch) >= minActionInterval {
				if setMinReplicas(clientset, floorMinReplicas) {
					lastPatch = now
				}
			}
		}
	}
}

// setMinReplicas patches the HPA's minReplicas, clamped to [floor, hpa.maxReplicas].
// Returns true only if it actually changed the value.
func setMinReplicas(clientset *kubernetes.Clientset, desired int32) bool {
	hpaClient := clientset.AutoscalingV2().HorizontalPodAutoscalers(namespace)
	hpa, err := hpaClient.Get(context.TODO(), hpaName, metav1.GetOptions{})
	if err != nil {
		fmt.Printf("❌ Failed to get HPA %s: %v\n", hpaName, err)
		return false
	}

	// Guardrails: never below the floor, never above the HPA's own cap.
	if desired < floorMinReplicas {
		desired = floorMinReplicas
	}
	if desired > hpa.Spec.MaxReplicas {
		desired = hpa.Spec.MaxReplicas
	}
	if hpa.Spec.MinReplicas != nil && *hpa.Spec.MinReplicas == desired {
		return false // already there, skip the no-op write
	}

	hpa.Spec.MinReplicas = &desired
	if _, err := hpaClient.Update(context.TODO(), hpa, metav1.UpdateOptions{}); err != nil {
		fmt.Printf("❌ Failed to patch HPA: %v\n", err)
		return false
	}
	fmt.Printf("✅ Set %s minReplicas=%d\n", hpaName, desired)
	return true
}

func fetchPrediction() (PredictionResponse, bool) {
	// DYNAMIC URL: service name in-cluster, localhost when run on a laptop.
	targetURL := os.Getenv("BRAIN_URL")
	if targetURL == "" {
		targetURL = "http://localhost:8081/predict"
	}

	resp, err := http.Get(targetURL)
	if err != nil {
		fmt.Printf("❌ Error talking to Brain (%s): %v\n", targetURL, err)
		return PredictionResponse{}, false
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var pred PredictionResponse
	if err := json.Unmarshal(body, &pred); err != nil {
		fmt.Printf("❌ Bad prediction payload: %v\n", err)
		return PredictionResponse{}, false
	}
	return pred, true
}

func mustConnect() *kubernetes.Clientset {
	// Auto-detect: in-cluster config, else fall back to local kubeconfig.
	config, err := rest.InClusterConfig()
	if err != nil {
		var kubeconfig *string
		if home := homedir.HomeDir(); home != "" {
			kubeconfig = flag.String("kubeconfig", filepath.Join(home, ".kube", "config"), "(optional) absolute path to the kubeconfig file")
		} else {
			kubeconfig = flag.String("kubeconfig", "", "absolute path to the kubeconfig file")
		}
		flag.Parse()
		config, err = clientcmd.BuildConfigFromFlags("", *kubeconfig)
		if err != nil {
			panic(err.Error())
		}
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		panic(err.Error())
	}
	return clientset
}

func sendSlackAlert(msg string) {
	if SLACK_WEBHOOK_URL == "MOCK" {
		fmt.Println("\n---------------------------------------------------")
		fmt.Println("📢 [MOCK SLACK ALERT SENT]")
		fmt.Println(msg)
		fmt.Println("---------------------------------------------------")
		return
	}

	payload := SlackMessage{Text: msg}
	jsonPayload, _ := json.Marshal(payload)

	resp, err := http.Post(SLACK_WEBHOOK_URL, "application/json", bytes.NewBuffer(jsonPayload))
	if err != nil {
		fmt.Printf("❌ Failed to send Slack alert: %v\n", err)
		return
	}
	defer resp.Body.Close()
	fmt.Println("🔔 Slack Alert Sent!")
}
