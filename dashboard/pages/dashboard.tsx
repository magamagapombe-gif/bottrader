import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/router";
import { validateToken, getAllUsers, sendCommand, loadToken, clearToken } from "../lib/api";

interface UserStatus {
  id: string;
  username: string;
  is_online: boolean;
  last_seen: string | null;
  last_status: {
    balance: number;
    session_profit: number;
    pair: string;
    grid_size: number;
    cycle: number;
    loss_streak: number;
    is_running: boolean;
    campaign_goal: number;
    campaign_earned: number;
    updated_at: string;
  } | null;
  tokens: { id: string; role: string; revoked: boolean; expires_at: string | null; created_at: string }[];
}

export default function Dashboard() {
  const router = useRouter();
  const [role, setRole]       = useState<string>("");
  const [myUser, setMyUser]   = useState<string>("");
  const [users, setUsers]     = useState<UserStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab]         = useState<"dashboard" | "admin">("dashboard");
  const [cmdLoading, setCmdLoading] = useState<Record<string, boolean>>({});

  const token = loadToken();

  const loadData = useCallback(async () => {
    if (!token) { router.push("/"); return; }
    const val = await validateToken(token);
    if (!val.valid) { clearToken(); router.push("/"); return; }
    setRole(val.role);
    setMyUser(val.username);
    if (val.role === "admin") {
      const all = await getAllUsers();
      setUsers(all);
    } else {
      // regular user: fetch their own data only
      const all = await getAllUsers().catch(() => []);
      setUsers(all.filter((u: UserStatus) => u.username === val.username));
    }
    setLoading(false);
  }, [token, router]);

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 30000);
    return () => clearInterval(iv);
  }, [loadData]);

  async function handleCommand(userId: string, cmd: "stop" | "start") {
    setCmdLoading(p => ({ ...p, [userId]: true }));
    await sendCommand(userId, cmd);
    setTimeout(() => {
      setCmdLoading(p => ({ ...p, [userId]: false }));
      loadData();
    }, 2000);
  }

  if (loading) return <div style={styles.page}><p style={{ color:"#64748b", fontFamily:"sans-serif" }}>Loading...</p></div>;

  return (
    <div style={styles.page}>
      {/* Nav */}
      <nav style={styles.nav}>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <span style={styles.dot} />
          <span style={styles.navTitle}>SuperEye</span>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          <button style={tab==="dashboard" ? styles.tabActive : styles.tabInactive}
                  onClick={() => setTab("dashboard")}>Dashboard</button>
          {role === "admin" &&
            <button style={tab==="admin" ? styles.tabActive : styles.tabInactive}
                    onClick={() => setTab("admin")}>Admin</button>}
          <span style={styles.userPill}>{myUser}</span>
          <button style={styles.logoutBtn} onClick={() => { clearToken(); router.push("/"); }}>Logout</button>
        </div>
      </nav>

      <main style={styles.main}>
        {tab === "dashboard" && <UserGrid users={users} onCommand={handleCommand} cmdLoading={cmdLoading} />}
        {tab === "admin" && role === "admin" && <AdminPanel users={users} onRefresh={loadData} />}
      </main>
    </div>
  );
}

// ── User Grid ────────────────────────────────────────────────────────────────
function UserGrid({ users, onCommand, cmdLoading }:
  { users: UserStatus[]; onCommand: (id:string, cmd:"stop"|"start") => void; cmdLoading: Record<string,boolean> }) {
  if (!users.length) return <p style={{ color:"#64748b", fontFamily:"sans-serif" }}>No users found.</p>;
  return (
    <div style={styles.grid}>
      {users.map(u => <UserCard key={u.id} user={u} onCommand={onCommand} loading={!!cmdLoading[u.id]} />)}
    </div>
  );
}

function UserCard({ user, onCommand, loading }:
  { user: UserStatus; onCommand: (id:string, cmd:"stop"|"start") => void; loading: boolean }) {
  const s   = user.last_status;
  const pct = s && s.campaign_goal > 0 ? Math.min(100, s.campaign_earned / s.campaign_goal * 100) : 0;
  const online   = user.is_online;
  const lastSeen = user.last_seen
    ? new Date(user.last_seen).toLocaleString()
    : "Never";

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          <span style={{ ...styles.statusDot, background: online ? "#00c896" : "#ef4444" }} />
          <span style={styles.username}>{user.username}</span>
        </div>
        <span style={{ ...styles.pill, background: online ? "#00c89622" : "#ef444422",
                        color: online ? "#00c896" : "#ef4444" }}>
          {online ? "Online" : "Offline"}
        </span>
      </div>

      {s ? <>
        {/* Stats */}
        <div style={styles.statsRow}>
          <Stat label="Balance"     value={`$${s.balance.toFixed(2)}`} />
          <Stat label="Session P&L" value={`$${s.session_profit >= 0 ? "+" : ""}${s.session_profit.toFixed(2)}`}
                color={s.session_profit >= 0 ? "#00c896" : "#ef4444"} />
          <Stat label="Cycle"       value={String(s.cycle)} />
        </div>

        {/* Pair / Grid */}
        <div style={{ display:"flex", gap:8, margin:"12px 0" }}>
          <span style={styles.badge}>{s.pair}</span>
          <span style={styles.badge}>Grid {s.grid_size}</span>
          <span style={styles.badge}>Streak {s.loss_streak}</span>
        </div>

        {/* Campaign bar */}
        <div style={{ marginBottom:12 }}>
          <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
            <span style={styles.label}>Campaign</span>
            <span style={styles.label}>${s.campaign_earned.toFixed(2)} / ${s.campaign_goal.toFixed(2)}</span>
          </div>
          <div style={styles.barBg}>
            <div style={{ ...styles.barFill, width:`${pct}%` }} />
          </div>
          <span style={{ ...styles.label, color:"#64748b" }}>{pct.toFixed(1)}%</span>
        </div>
      </> : (
        <p style={{ color:"#64748b", fontSize:13, fontFamily:"sans-serif", marginBottom:16 }}>No data yet</p>
      )}

      {/* Controls */}
      <div style={{ display:"flex", gap:8 }}>
        <button style={styles.stopBtn} disabled={loading || !online}
                onClick={() => onCommand(user.id, "stop")}>
          {loading ? "..." : "Stop after cycle"}
        </button>
      </div>

      <p style={{ color:"#374151", fontSize:11, marginTop:8, fontFamily:"sans-serif" }}>
        Last seen: {lastSeen}
      </p>
    </div>
  );
}

function Stat({ label, value, color }: { label:string; value:string; color?:string }) {
  return (
    <div style={{ flex:1 }}>
      <div style={{ color:"#64748b", fontSize:11, fontFamily:"sans-serif", marginBottom:2 }}>{label}</div>
      <div style={{ color: color || "#e2e8f0", fontSize:18, fontWeight:700, fontFamily:"sans-serif" }}>{value}</div>
    </div>
  );
}

// ── Admin Panel ──────────────────────────────────────────────────────────────
import { issueToken, revokeToken } from "../lib/api";

function AdminPanel({ users, onRefresh }: { users: UserStatus[]; onRefresh: () => void }) {
  const [username, setUsername] = useState("");
  const [role, setRole]         = useState("user");
  const [expires, setExpires]   = useState("");
  const [newToken, setNewToken] = useState("");
  const [issuing, setIssuing]   = useState(false);
  const [revoking, setRevoking] = useState<Record<string,boolean>>({});

  async function handleIssue(e: React.FormEvent) {
    e.preventDefault();
    setIssuing(true);
    const result = await issueToken(username, role, expires ? parseInt(expires) : null);
    setIssuing(false);
    if (result.token) {
      setNewToken(result.token);
      setUsername(""); setExpires("");
      onRefresh();
    }
  }

  async function handleRevoke(tokenId: string) {
    setRevoking(p => ({ ...p, [tokenId]: true }));
    await revokeToken(tokenId);
    setTimeout(() => { setRevoking(p => ({ ...p, [tokenId]: false })); onRefresh(); }, 1000);
  }

  return (
    <div>
      {/* Issue token form */}
      <div style={styles.adminCard}>
        <h2 style={styles.sectionTitle}>Issue new token</h2>
        <form onSubmit={handleIssue} style={{ display:"flex", gap:10, flexWrap:"wrap", alignItems:"flex-end" }}>
          <div>
            <label style={styles.label}>Username</label>
            <input style={styles.smallInput} value={username}
                   onChange={e => setUsername(e.target.value)} placeholder="alice" required />
          </div>
          <div>
            <label style={styles.label}>Role</label>
            <select style={styles.smallInput} value={role} onChange={e => setRole(e.target.value)}>
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div>
            <label style={styles.label}>Expires (days, blank = never)</label>
            <input style={styles.smallInput} type="number" value={expires}
                   onChange={e => setExpires(e.target.value)} placeholder="30" min={1} />
          </div>
          <button style={styles.issueBtn} type="submit" disabled={issuing || !username}>
            {issuing ? "Generating..." : "Generate token"}
          </button>
        </form>

        {newToken && (
          <div style={styles.tokenBox}>
            <span style={{ color:"#64748b", fontSize:12, fontFamily:"sans-serif" }}>New token (copy now — shown once):</span>
            <div style={{ display:"flex", gap:8, alignItems:"center", marginTop:6 }}>
              <code style={styles.tokenCode}>{newToken}</code>
              <button style={styles.copyBtn} onClick={() => navigator.clipboard.writeText(newToken)}>Copy</button>
            </div>
          </div>
        )}
      </div>

      {/* Users table */}
      <div style={styles.adminCard}>
        <h2 style={styles.sectionTitle}>All users</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              {["Username","Role","Status","Created","Expires","Token ID","Actions"].map(h =>
                <th key={h} style={styles.th}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {users.map(u => {
              const tk = u.tokens?.[0];
              return (
                <tr key={u.id} style={styles.tr}>
                  <td style={styles.td}>{u.username}</td>
                  <td style={styles.td}>
                    <span style={{ ...styles.pill, background:"#7c3aed22", color:"#a78bfa" }}>
                      {tk?.role || "—"}
                    </span>
                  </td>
                  <td style={styles.td}>
                    {tk?.revoked
                      ? <span style={{ color:"#ef4444", fontSize:12 }}>Revoked</span>
                      : <span style={{ color:"#00c896", fontSize:12 }}>Active</span>}
                  </td>
                  <td style={styles.td}>
                    {tk?.created_at ? new Date(tk.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td style={styles.td}>
                    {tk?.expires_at ? new Date(tk.expires_at).toLocaleDateString() : "Never"}
                  </td>
                  <td style={styles.td}>
                    <code style={{ fontSize:11, color:"#64748b" }}>{tk?.id?.slice(0,12)}...</code>
                  </td>
                  <td style={styles.td}>
                    {!tk?.revoked && (
                      <button style={styles.revokeBtn}
                              disabled={revoking[tk?.id || ""]}
                              onClick={() => tk && handleRevoke(tk.id)}>
                        {revoking[tk?.id || ""] ? "..." : "Revoke"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  page:        { minHeight:"100vh", background:"#0f1117", color:"#e2e8f0" },
  nav:         { display:"flex", justifyContent:"space-between", alignItems:"center",
                 padding:"0 24px", height:56, background:"#1a1d27",
                 borderBottom:"1px solid #2d3148", position:"sticky", top:0, zIndex:10 },
  navTitle:    { color:"#e2e8f0", fontWeight:700, fontSize:18, fontFamily:"sans-serif" },
  dot:         { width:10, height:10, borderRadius:"50%", background:"#00c896", display:"inline-block" },
  tabActive:   { background:"#00c896", color:"#000", border:"none", borderRadius:6,
                 padding:"6px 14px", fontWeight:700, cursor:"pointer", fontFamily:"sans-serif", fontSize:13 },
  tabInactive: { background:"transparent", color:"#64748b", border:"1px solid #2d3148",
                 borderRadius:6, padding:"6px 14px", cursor:"pointer", fontFamily:"sans-serif", fontSize:13 },
  userPill:    { background:"#262a36", color:"#94a3b8", borderRadius:6,
                 padding:"4px 10px", fontSize:12, fontFamily:"monospace" },
  logoutBtn:   { background:"transparent", color:"#64748b", border:"none",
                 cursor:"pointer", fontSize:13, fontFamily:"sans-serif" },
  main:        { maxWidth:1200, margin:"0 auto", padding:"24px 16px" },
  grid:        { display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(340px,1fr))", gap:16 },
  card:        { background:"#1a1d27", borderRadius:12, padding:20,
                 border:"1px solid #2d3148" },
  statsRow:    { display:"flex", gap:8 },
  statusDot:   { width:8, height:8, borderRadius:"50%", display:"inline-block" },
  username:    { color:"#e2e8f0", fontWeight:700, fontSize:15, fontFamily:"sans-serif" },
  pill:        { borderRadius:20, padding:"2px 10px", fontSize:12, fontFamily:"sans-serif", fontWeight:600 },
  badge:       { background:"#262a36", color:"#94a3b8", borderRadius:6,
                 padding:"2px 8px", fontSize:12, fontFamily:"monospace" },
  label:       { color:"#94a3b8", fontSize:12, fontFamily:"sans-serif" },
  barBg:       { background:"#262a36", borderRadius:4, height:6, overflow:"hidden", marginBottom:4 },
  barFill:     { background:"#00c896", height:"100%", borderRadius:4, transition:"width 0.5s" },
  stopBtn:     { flex:1, background:"#ef44440d", color:"#ef4444", border:"1px solid #ef444433",
                 borderRadius:8, padding:"8px", cursor:"pointer", fontFamily:"sans-serif",
                 fontSize:13, fontWeight:600 },
  adminCard:   { background:"#1a1d27", borderRadius:12, padding:20, border:"1px solid #2d3148", marginBottom:20 },
  sectionTitle:{ color:"#e2e8f0", fontWeight:700, fontSize:16, fontFamily:"sans-serif", marginBottom:16, marginTop:0 },
  smallInput:  { background:"#262a36", border:"1px solid #2d3148", borderRadius:6,
                 color:"#e2e8f0", padding:"8px 10px", fontSize:13, fontFamily:"sans-serif",
                 display:"block", marginTop:4, outline:"none" },
  issueBtn:    { background:"#00c896", color:"#000", border:"none", borderRadius:8,
                 padding:"10px 20px", fontWeight:700, cursor:"pointer", fontFamily:"sans-serif", fontSize:13 },
  tokenBox:    { marginTop:16, background:"#0f1117", borderRadius:8, padding:14, border:"1px solid #00c89633" },
  tokenCode:   { background:"#262a36", color:"#00c896", padding:"6px 12px", borderRadius:6,
                 fontSize:13, fontFamily:"monospace", flex:1, wordBreak:"break-all" },
  copyBtn:     { background:"#262a36", color:"#94a3b8", border:"none", borderRadius:6,
                 padding:"6px 12px", cursor:"pointer", fontFamily:"sans-serif", fontSize:12 },
  table:       { width:"100%", borderCollapse:"collapse" },
  th:          { color:"#64748b", fontSize:12, fontFamily:"sans-serif", textAlign:"left",
                 padding:"8px 12px", borderBottom:"1px solid #2d3148" },
  tr:          { borderBottom:"1px solid #1e2235" },
  td:          { color:"#94a3b8", fontSize:13, fontFamily:"sans-serif", padding:"10px 12px", verticalAlign:"middle" },
  revokeBtn:   { background:"#ef44440d", color:"#ef4444", border:"1px solid #ef444433",
                 borderRadius:6, padding:"4px 12px", cursor:"pointer", fontFamily:"sans-serif", fontSize:12 },
};
