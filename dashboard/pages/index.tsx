import { useState } from "react";
import { useRouter } from "next/router";
import { validateToken, saveToken } from "../lib/api";

export default function Login() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const result = await validateToken(token.trim());
    setLoading(false);
    if (!result.valid) {
      setError(result.reason || "Invalid token");
      return;
    }
    saveToken(token.trim());
    router.push("/dashboard");
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <span style={styles.dot} />
          <span style={styles.title}>SuperEye</span>
        </div>
        <p style={styles.sub}>Enter your access token to continue</p>
        <form onSubmit={handleLogin}>
          <input
            style={styles.input}
            type="text"
            placeholder="se-xxxxxxxxxxxxxxxxxxxxxxxx"
            value={token}
            onChange={e => setToken(e.target.value)}
            autoFocus
          />
          {error && <p style={styles.error}>{error}</p>}
          <button style={styles.btn} type="submit" disabled={loading || !token}>
            {loading ? "Validating..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page:  { minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center", background:"#0f1117" },
  card:  { background:"#1a1d27", borderRadius:16, padding:"40px 36px", width:380, boxShadow:"0 8px 32px #0006" },
  logo:  { display:"flex", alignItems:"center", gap:10, marginBottom:8 },
  dot:   { width:12, height:12, borderRadius:"50%", background:"#00c896", display:"inline-block" },
  title: { color:"#e2e8f0", fontSize:24, fontWeight:700, fontFamily:"sans-serif" },
  sub:   { color:"#64748b", fontSize:14, marginBottom:24, fontFamily:"sans-serif" },
  input: { width:"100%", background:"#262a36", border:"1px solid #2d3148", borderRadius:8,
           padding:"10px 14px", color:"#e2e8f0", fontSize:14, marginBottom:12,
           boxSizing:"border-box", fontFamily:"monospace", outline:"none" },
  error: { color:"#ef4444", fontSize:13, marginBottom:12, fontFamily:"sans-serif" },
  btn:   { width:"100%", background:"#00c896", color:"#000", border:"none", borderRadius:8,
           padding:"11px", fontSize:15, fontWeight:700, cursor:"pointer", fontFamily:"sans-serif" },
};
