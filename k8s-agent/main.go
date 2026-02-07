package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os" // <--- Added for reading Env Vars
	"path/filepath"
	"time"

	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/client-go/util/homedir"
)

// If you ever get Slack, paste the URL here. For now, we use "MOCK".
const SLACK_WEBHOOK_URL = "MOCK"

type PredictionResponse struct {
	CurrentCPU   float64 `json:"current_cpu"`
	PredictedCPU float64 `json:"predicted_cpu"`
	Action       string  `json:"action"`
	Status       string  `json:"status"`
}

type SlackMessage struct {
	Text string `json:"text"`
}

func main() {
	fmt.Println("🤖 Sentinel Agent Starting (Cluster Mode)...")

	// 1. Connect to Kubernetes (Auto-detects if inside cluster or local)
	config, err := rest.InClusterConfig()
	if err != nil {
		// Fallback to local kubeconfig (for testing on laptop)
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

	fmt.Println("✅ Connected to Kubernetes Cluster!")

	// 2. The Loop
	for {
		time.Sleep(5 * time.Second)

		// DYNAMIC URL: If running in K8s, use the Service Name. If local, use localhost.
		targetURL := os.Getenv("BRAIN_URL")
		if targetURL == "" {
			targetURL = "http://localhost:8081/predict"
		}
		
		resp, err := http.Get(targetURL)
		if err != nil {
			fmt.Printf("❌ Error talking to Brain (%s): %v\n", targetURL, err)
			continue
		}
		defer resp.Body.Close()

		body, _ := io.ReadAll(resp.Body)
		var prediction PredictionResponse
		json.Unmarshal(body, &prediction)

		if prediction.Status == "warning" {
			fmt.Println("⏳ Waiting for data...")
			continue
		}

		fmt.Printf("🧠 CPU: %.4f | Action: %s\n", prediction.CurrentCPU, prediction.Action)

		if prediction.Action == "scale_up" {
			fmt.Println("⚠️ ALERT: Scaling Up...")
			scaleUpMemory(clientset)
			sendSlackAlert("🚨 *Sentinel Ops Alert* 🚨\nDetected CPU spike! Automatically scaling up `victim-app` to prevent crash.")
			time.Sleep(60 * time.Second) // Cooldown
		}
	}
}

func scaleUpMemory(clientset *kubernetes.Clientset) {
	deploymentsClient := clientset.AppsV1().Deployments("default")
	deployment, err := deploymentsClient.Get(context.TODO(), "victim-app", metav1.GetOptions{})
	if err != nil {
		fmt.Printf("❌ Failed to find victim-app: %v\n", err)
		return
	}

	deployment.Spec.Template.Spec.Containers[0].Resources.Limits["memory"] = resource.MustParse("128Mi")
	_, err = deploymentsClient.Update(context.TODO(), deployment, metav1.UpdateOptions{})
	if err != nil {
		fmt.Printf("❌ Failed to update: %v\n", err)
	} else {
		fmt.Println("✅ SUCCESS: Scaled Up!")
	}
}

func sendSlackAlert(msg string) {
	if SLACK_WEBHOOK_URL == "MOCK" {
		fmt.Println("\n---------------------------------------------------")
		fmt.Println("📢 [MOCK SLACK ALERT SENT]")
		fmt.Println(msg)
		fmt.Println("---------------------------------------------------\n")
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