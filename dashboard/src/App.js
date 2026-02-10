import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

function App() {
  const [dataPoints, setDataPoints] = useState([]);
  const [systemStatus, setSystemStatus] = useState("NORMAL");
  const [logs, setLogs] = useState([]);

  // Fetch data every 2 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        // Fetch from the Brain
        const response = await fetch('http://localhost:8081/predict');
        const data = await response.json();
        
        // Destructure the response (Note: data.current_cpu, NOT current_cpu)
        const { current_cpu, predicted_cpu, action } = data;
        const timestamp = new Date().toLocaleTimeString();

        // 1. Update Graph Data
        setDataPoints(prev => {
          // Create new point
          const newPoint = { 
            time: timestamp, 
            cpu: current_cpu, 
            pred: predicted_cpu 
          };
          // Keep only last 20 points
          const newData = [...prev, newPoint];
          return newData.slice(-20); 
        });

        // 2. Update Status (THE FIX IS HERE)
        // We now check for "SCALING", which matches the Python backend.
        if (action === "SCALING") {
          setSystemStatus("CRITICAL - SCALING UP");
          // Add to log (Trigger the state update)
          setLogs(prev => [`⚠️ Alert! CPU: ${current_cpu.toFixed(2)}% | Pred: ${predicted_cpu.toFixed(2)}%`, ...prev].slice(0, 5));
        } else {
          setSystemStatus("NORMAL");
        }

      } catch (error) {
        console.error("Error fetching data:", error);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, []);

  const addLog = (msg) => {
    setLogs(prev => [msg, ...prev].slice(0, 5));
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial', backgroundColor: '#1e1e1e', color: 'white', minHeight: '100vh' }}>
      <h1>🛡️ Sentinel Ops: AI Supervisor</h1>
      
      {/* Status Badge */}
      <div style={{ 
        padding: '15px', 
        borderRadius: '8px', 
        marginBottom: '20px',
        backgroundColor: systemStatus.includes("CRITICAL") ? '#ff4d4d' : '#4caf50',
        textAlign: 'center',
        fontSize: '24px',
        fontWeight: 'bold'
      }}>
        SYSTEM STATUS: {systemStatus}
      </div>

      {/* Graph */}
      <div style={{ height: '300px', backgroundColor: '#2d2d2d', padding: '20px', borderRadius: '8px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={dataPoints}>
            <CartesianGrid strokeDasharray="3 3" stroke="#444" />
            <XAxis dataKey="time" stroke="#ccc" />
            <YAxis stroke="#ccc" />
            <Tooltip contentStyle={{ backgroundColor: '#333', border: 'none' }} />
            <Legend />
            <Line type="monotone" dataKey="cpu" stroke="#8884d8" name="Actual CPU" strokeWidth={3} dot={false} />
            <Line type="monotone" dataKey="pred" stroke="#82ca9d" name="AI Prediction" strokeWidth={3} strokeDasharray="5 5" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Action Logs */}
      <div style={{ marginTop: '20px' }}>
        <h3>🤖 Autonomous Actions Log</h3>
        <div style={{ backgroundColor: '#111', padding: '10px', borderRadius: '5px', fontFamily: 'monospace' }}>
          {logs.length === 0 ? <p style={{color: '#666'}}>No critical actions taken yet...</p> : logs.map((log, i) => (
            <div key={i} style={{ borderBottom: '1px solid #333', padding: '5px 0', color: '#ffcc00' }}>
              {log}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;