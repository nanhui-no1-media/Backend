import { useState } from "react";

export default function App() {
  const [count, setCount] = useState(0);

  return (
    <div style={{ padding: 32, fontFamily: "sans-serif" }}>
      <h1>React + TypeScript + Webpack</h1>
      <button onClick={() => setCount((c) => c + 1)}>count: {count}</button>
    </div>
  );
}
