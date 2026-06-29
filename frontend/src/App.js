import { useEffect } from "react";

function App() {
  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then(r => r.json())
      .then(data => console.log(data));
  }, []);

  return <div>Calibration App</div>;
}

export default App;