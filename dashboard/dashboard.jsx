/**
 * Client Review Prep Dashboard
 *
 * Advisor-facing view showing upcoming reviews, prep status,
 * client engagement health, and briefing cards.
 *
 * The paraplanner uses the "Upcoming Reviews" tab Monday morning.
 * The advisor uses "Client Briefings" before each meeting.
 * The principal uses "Engagement Health" in monthly pipeline reviews.
 */

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Cell,
} from "recharts";

// ============================================================================
// SYNTHETIC DATA
// ============================================================================

const CLIENTS = [
  {
    id: "HH-001",
    name: "The Henderson Household",
    primary: "Robert Henderson",
    spouse: "Margaret Henderson",
    tier: "gold",
    advisor: "Michelle Torres",
    clientSince: "2017",
    aum: 1240000,
    aumChange: 34.9,
    nextReview: "Mar 15",
    nextReviewDays: 12,
    lastReview: "Nov 28",
    reviewStatus: "auto_assembled",
    engagementScore: 80,
    engagementLevel: "strong",
    attritionRisk: "low",
    flags: {
      high: 4,
      medium: 2,
      items: [
        { severity: "high", title: "Financial plan is 15 months old", detail: "Predates Margaret's retirement" },
        { severity: "high", title: "Overdue: LTC insurance research", detail: "65 days overdue, assigned to Michelle Torres" },
        { severity: "high", title: "Overdue: Beneficiary designations", detail: "30 days overdue, assigned to Sarah Kim" },
        { severity: "high", title: "Potential inheritance", detail: "Robert's mother passed — estate in probate" },
        { severity: "medium", title: "RTQ expiring in 29 days", detail: "Schedule renewal at meeting" },
        { severity: "medium", title: "Vacation home goal at risk", detail: "45% funded, timeline may need adjustment" },
      ],
    },
    conversationStarters: [
      "Ask how Margaret is adjusting to retirement. Any changes to spending?",
      "Express condolences re: Robert's mother. Ask about estate timeline.",
      "Vacation home goal at risk — discuss adjusting target or timeline.",
    ],
    performance: { returnPct: 8.3, benchmarkPct: 7.1, excessPct: 1.2 },
    signalScores: [
      { signal: "Meeting Attendance", score: 100 },
      { signal: "Response Time", score: 100 },
      { signal: "Interaction Freq", score: 73 },
      { signal: "AUM Trend", score: 100 },
      { signal: "Portal Activity", score: 30 },
      { signal: "Doc Compliance", score: 40 },
    ],
    actionItems: [
      { desc: "Research LTC insurance options", status: "overdue", daysOverdue: 65, assignee: "Michelle Torres" },
      { desc: "Update beneficiary designations on rollover IRA", status: "overdue", daysOverdue: 30, assignee: "Sarah Kim" },
    ],
  },
  {
    id: "HH-002",
    name: "The Chen Household",
    primary: "David Chen",
    spouse: null,
    tier: "silver",
    advisor: "Michelle Torres",
    clientSince: "2021",
    aum: 279000,
    aumChange: -10.0,
    nextReview: "Feb 16",
    nextReviewDays: -15,
    lastReview: "Aug 15",
    reviewStatus: "auto_assembled",
    engagementScore: 21,
    engagementLevel: "at_risk",
    attritionRisk: "high",
    flags: {
      high: 3,
      medium: 0,
      items: [
        { severity: "high", title: "Review 15 days overdue", detail: "Client has not responded to 3 scheduling attempts" },
        { severity: "high", title: "IPS and RTQ both expired", detail: "Last updated March 2024" },
        { severity: "high", title: "AUM declining with outflows", detail: "$35k net outflows, -10% change" },
      ],
    },
    conversationStarters: [
      "It's been 7 months since last review. Check on any major life changes.",
      "401k contribution increase — was this actioned? Client may feel neglected.",
    ],
    performance: { returnPct: -2.1, benchmarkPct: 3.8, excessPct: -5.9 },
    signalScores: [
      { signal: "Meeting Attendance", score: 0 },
      { signal: "Response Time", score: 0 },
      { signal: "Interaction Freq", score: 70 },
      { signal: "AUM Trend", score: 35 },
      { signal: "Portal Activity", score: 30 },
      { signal: "Doc Compliance", score: 0 },
    ],
    actionItems: [
      { desc: "Increase 401k contribution to maximize match", status: "overdue", daysOverdue: 170, assignee: "Michelle Torres" },
    ],
  },
  {
    id: "HH-003",
    name: "The Patel Household",
    primary: "Anika Patel",
    spouse: "Raj Patel",
    tier: "platinum",
    advisor: "James Wright",
    clientSince: "2014",
    aum: 3180000,
    aumChange: 6.2,
    nextReview: "Mar 22",
    nextReviewDays: 19,
    lastReview: "Dec 18",
    reviewStatus: "reviewed",
    engagementScore: 91,
    engagementLevel: "strong",
    attritionRisk: "low",
    flags: {
      high: 0,
      medium: 1,
      items: [
        { severity: "medium", title: "Estate plan last updated 2022", detail: "Review given Raj's business sale last year" },
      ],
    },
    conversationStarters: [
      "Ask about Raj's consulting work since selling the business.",
      "Anika mentioned wanting to fund a donor-advised fund — follow up.",
    ],
    performance: { returnPct: 6.2, benchmarkPct: 7.1, excessPct: -0.9 },
    signalScores: [
      { signal: "Meeting Attendance", score: 100 },
      { signal: "Response Time", score: 90 },
      { signal: "Interaction Freq", score: 95 },
      { signal: "AUM Trend", score: 85 },
      { signal: "Portal Activity", score: 80 },
      { signal: "Doc Compliance", score: 90 },
    ],
    actionItems: [],
  },
  {
    id: "HH-004",
    name: "The Morales Household",
    primary: "Sofia Morales",
    spouse: "Carlos Morales",
    tier: "gold",
    advisor: "James Wright",
    clientSince: "2019",
    aum: 890000,
    aumChange: 12.4,
    nextReview: "Mar 10",
    nextReviewDays: 7,
    lastReview: "Sep 8",
    reviewStatus: "auto_assembled",
    engagementScore: 68,
    engagementLevel: "healthy",
    attritionRisk: "low",
    flags: {
      high: 1,
      medium: 2,
      items: [
        { severity: "high", title: "Overdue: Roth conversion analysis", detail: "42 days overdue, assigned to James Wright" },
        { severity: "medium", title: "IPS expiring in 45 days", detail: "Schedule renewal" },
        { severity: "medium", title: "College goal for twins at risk", detail: "28% funded, 529 contributions paused" },
      ],
    },
    conversationStarters: [
      "Sofia mentioned potentially going part-time — follow up on timeline.",
      "Roth conversion analysis was promised last meeting. Have it ready.",
    ],
    performance: { returnPct: 12.4, benchmarkPct: 7.1, excessPct: 5.3 },
    signalScores: [
      { signal: "Meeting Attendance", score: 80 },
      { signal: "Response Time", score: 65 },
      { signal: "Interaction Freq", score: 55 },
      { signal: "AUM Trend", score: 80 },
      { signal: "Portal Activity", score: 50 },
      { signal: "Doc Compliance", score: 60 },
    ],
    actionItems: [
      { desc: "Complete Roth conversion analysis", status: "overdue", daysOverdue: 42, assignee: "James Wright" },
    ],
  },
];

const FIRM_STATS = {
  totalHouseholds: 203,
  totalAum: 382000000,
  reviewsDue30d: 18,
  reviewsOverdue: 3,
  avgEngagement: 72,
  openActionItems: 47,
  overdueActionItems: 12,
  complianceIssues: 8,
};

// ============================================================================
// THEME
// ============================================================================

const C = {
  bg: "#fafaf9",
  surface: "#ffffff",
  surfaceMuted: "#f5f5f4",
  border: "#e7e5e4",
  borderStrong: "#d6d3d1",
  text: "#1c1917",
  textMuted: "#78716c",
  textDim: "#a8a29e",
  green: "#16a34a",
  greenBg: "#f0fdf4",
  greenBorder: "#bbf7d0",
  amber: "#d97706",
  amberBg: "#fffbeb",
  amberBorder: "#fde68a",
  red: "#dc2626",
  redBg: "#fef2f2",
  redBorder: "#fecaca",
  blue: "#2563eb",
  blueBg: "#eff6ff",
  blueBorder: "#bfdbfe",
  purple: "#7c3aed",
};

// ============================================================================
// COMPONENTS
// ============================================================================

const Badge = ({ children, variant = "default" }) => {
  const styles = {
    critical: { bg: C.redBg, color: C.red, border: C.redBorder },
    high: { bg: C.redBg, color: C.red, border: C.redBorder },
    warning: { bg: C.amberBg, color: C.amber, border: C.amberBorder },
    medium: { bg: C.amberBg, color: C.amber, border: C.amberBorder },
    healthy: { bg: C.greenBg, color: C.green, border: C.greenBorder },
    strong: { bg: C.greenBg, color: C.green, border: C.greenBorder },
    low: { bg: C.greenBg, color: C.green, border: C.greenBorder },
    at_risk: { bg: C.redBg, color: C.red, border: C.redBorder },
    platinum: { bg: "#f5f3ff", color: C.purple, border: "#ddd6fe" },
    gold: { bg: C.amberBg, color: C.amber, border: C.amberBorder },
    silver: { bg: C.surfaceMuted, color: C.textMuted, border: C.border },
    reviewed: { bg: C.greenBg, color: C.green, border: C.greenBorder },
    auto_assembled: { bg: C.blueBg, color: C.blue, border: C.blueBorder },
    overdue: { bg: C.redBg, color: C.red, border: C.redBorder },
    default: { bg: C.surfaceMuted, color: C.textMuted, border: C.border },
  };
  const s = styles[variant] || styles.default;
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 4,
      fontSize: 10, fontWeight: 600, backgroundColor: s.bg, color: s.color,
      border: `1px solid ${s.border}`, letterSpacing: "0.04em",
      textTransform: "uppercase", fontFamily: "'IBM Plex Mono', monospace",
    }}>
      {children}
    </span>
  );
};

const Card = ({ children, style = {}, onClick }) => (
  <div onClick={onClick} style={{
    backgroundColor: C.surface, border: `1px solid ${C.border}`,
    borderRadius: 8, padding: 20,
    cursor: onClick ? "pointer" : "default", ...style,
  }}>
    {children}
  </div>
);

const Metric = ({ value, label, color, small }) => (
  <div style={{ textAlign: "center" }}>
    <div style={{
      fontSize: small ? 20 : 26, fontWeight: 700,
      color: color || C.text, fontFamily: "'IBM Plex Mono', monospace", lineHeight: 1,
    }}>{value}</div>
    <div style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>{label}</div>
  </div>
);

const SectionLabel = ({ children }) => (
  <h2 style={{
    fontSize: 11, fontWeight: 600, color: C.textMuted,
    textTransform: "uppercase", letterSpacing: "0.08em",
    margin: "0 0 12px 0", fontFamily: "'IBM Plex Mono', monospace",
  }}>{children}</h2>
);

const ScoreBar = ({ score, width = 120 }) => {
  const color = score >= 80 ? C.green : score >= 60 ? C.amber : score >= 40 ? "#f59e0b" : C.red;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width, height: 6, backgroundColor: C.surfaceMuted, borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${score}%`, backgroundColor: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace", color, minWidth: 28 }}>
        {score}
      </span>
    </div>
  );
};

const EngagementRadar = ({ data }) => (
  <ResponsiveContainer width="100%" height={220}>
    <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
      <PolarGrid stroke={C.border} />
      <PolarAngleAxis dataKey="signal" tick={{ fontSize: 10, fill: C.textMuted }} />
      <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
      <Radar dataKey="score" stroke={C.blue} fill={C.blue} fillOpacity={0.15} strokeWidth={2} />
    </RadarChart>
  </ResponsiveContainer>
);

// ============================================================================
// MAIN DASHBOARD
// ============================================================================

export default function ReviewPrepDashboard() {
  const [activeTab, setActiveTab] = useState("reviews");
  const [selectedClient, setSelectedClient] = useState(null);

  const sortedByReview = [...CLIENTS].sort((a, b) => a.nextReviewDays - b.nextReviewDays);
  const sortedByEngagement = [...CLIENTS].sort((a, b) => a.engagementScore - b.engagementScore);

  return (
    <div style={{
      backgroundColor: C.bg, color: C.text, minHeight: "100vh",
      fontFamily: "'Inter', -apple-system, sans-serif", fontSize: 14,
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{
        borderBottom: `1px solid ${C.border}`, padding: "16px 28px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        backgroundColor: C.surface,
      }}>
        <div>
          <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Review Prep</h1>
          <span style={{ fontSize: 11, color: C.textDim }}>
            {FIRM_STATS.totalHouseholds} households — ${(FIRM_STATS.totalAum / 1e6).toFixed(0)}M AUM
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {FIRM_STATS.reviewsOverdue > 0 && (
            <div style={{
              padding: "5px 10px", borderRadius: 6, backgroundColor: C.redBg,
              border: `1px solid ${C.redBorder}`, fontSize: 11, fontWeight: 600, color: C.red,
            }}>
              {FIRM_STATS.reviewsOverdue} overdue reviews
            </div>
          )}
          <div style={{
            padding: "5px 10px", borderRadius: 6, backgroundColor: C.amberBg,
            border: `1px solid ${C.amberBorder}`, fontSize: 11, fontWeight: 600, color: C.amber,
          }}>
            {FIRM_STATS.overdueActionItems} overdue action items
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ borderBottom: `1px solid ${C.border}`, padding: "0 28px", backgroundColor: C.surface }}>
        {["reviews", "engagement", "briefing"].map((tab) => (
          <button key={tab} onClick={() => { setActiveTab(tab); setSelectedClient(null); }} style={{
            padding: "10px 16px", fontSize: 13,
            fontWeight: activeTab === tab ? 600 : 400,
            color: activeTab === tab ? C.text : C.textMuted,
            background: "none", border: "none",
            borderBottom: activeTab === tab ? `2px solid ${C.text}` : "2px solid transparent",
            cursor: "pointer", fontFamily: "inherit", textTransform: "capitalize",
          }}>
            {tab === "reviews" ? "Upcoming Reviews" : tab === "engagement" ? "Engagement Health" : "Client Briefing"}
          </button>
        ))}
      </div>

      <div style={{ padding: 28 }}>
        {/* Top Metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 24 }}>
          <Card><Metric value={FIRM_STATS.reviewsDue30d} label="Reviews Due (30d)" /></Card>
          <Card><Metric value={FIRM_STATS.reviewsOverdue} label="Overdue" color={C.red} /></Card>
          <Card><Metric value={FIRM_STATS.avgEngagement} label="Avg Engagement" color={C.green} /></Card>
          <Card><Metric value={FIRM_STATS.openActionItems} label="Open Action Items" /></Card>
          <Card><Metric value={FIRM_STATS.complianceIssues} label="Compliance Issues" color={C.amber} /></Card>
        </div>

        {activeTab === "reviews" && (
          <ReviewsTab clients={sortedByReview} selectedClient={selectedClient} setSelectedClient={setSelectedClient} />
        )}
        {activeTab === "engagement" && (
          <EngagementTab clients={sortedByEngagement} selectedClient={selectedClient} setSelectedClient={setSelectedClient} />
        )}
        {activeTab === "briefing" && (
          <BriefingTab clients={CLIENTS} selectedClient={selectedClient} setSelectedClient={setSelectedClient} />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// UPCOMING REVIEWS TAB
// ============================================================================

function ReviewsTab({ clients, selectedClient, setSelectedClient }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <SectionLabel>Review Schedule</SectionLabel>
      {clients.map((c) => {
        const isOverdue = c.nextReviewDays < 0;
        const isThisWeek = c.nextReviewDays >= 0 && c.nextReviewDays <= 7;
        const isSelected = selectedClient === c.id;
        const borderColor = isOverdue ? C.redBorder : isThisWeek ? C.amberBorder : C.border;

        return (
          <Card key={c.id} onClick={() => setSelectedClient(isSelected ? null : c.id)}
            style={{ borderColor, borderLeftWidth: 3 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{c.name}</span>
                  <Badge variant={c.tier}>{c.tier}</Badge>
                  {isOverdue && <Badge variant="overdue">overdue</Badge>}
                </div>
                <div style={{ fontSize: 12, color: C.textMuted }}>
                  {c.primary}{c.spouse ? ` & ${c.spouse}` : ""} — {c.advisor}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace", color: isOverdue ? C.red : C.text }}>
                  {c.nextReview}
                </div>
                <div style={{ fontSize: 11, color: isOverdue ? C.red : C.textDim }}>
                  {isOverdue ? `${Math.abs(c.nextReviewDays)} days overdue` : `in ${c.nextReviewDays} days`}
                </div>
              </div>
            </div>

            {/* Quick stats row */}
            <div style={{ display: "flex", gap: 24, marginTop: 12, paddingTop: 12, borderTop: `1px solid ${C.border}`, fontSize: 12 }}>
              <div>
                <span style={{ color: C.textDim }}>AUM: </span>
                <span style={{ fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace" }}>${(c.aum / 1000).toFixed(0)}k</span>
                <span style={{ color: c.aumChange >= 0 ? C.green : C.red, marginLeft: 4, fontFamily: "'IBM Plex Mono', monospace" }}>
                  {c.aumChange >= 0 ? "+" : ""}{c.aumChange}%
                </span>
              </div>
              <div>
                <span style={{ color: C.textDim }}>Prep: </span>
                <Badge variant={c.reviewStatus}>{c.reviewStatus.replace("_", " ")}</Badge>
              </div>
              <div>
                <span style={{ color: C.textDim }}>Flags: </span>
                {c.flags.high > 0 && <span style={{ color: C.red, fontWeight: 600 }}>{c.flags.high} high</span>}
                {c.flags.high > 0 && c.flags.medium > 0 && <span style={{ color: C.textDim }}>, </span>}
                {c.flags.medium > 0 && <span style={{ color: C.amber, fontWeight: 600 }}>{c.flags.medium} medium</span>}
                {c.flags.high === 0 && c.flags.medium === 0 && <span style={{ color: C.green, fontWeight: 600 }}>None</span>}
              </div>
              <div>
                <span style={{ color: C.textDim }}>Engagement: </span>
                <ScoreBar score={c.engagementScore} width={80} />
              </div>
            </div>

            {/* Expanded: flags */}
            {isSelected && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                <SectionLabel>Attention Flags</SectionLabel>
                {c.flags.items.map((f, i) => (
                  <div key={i} style={{
                    padding: "8px 12px", marginBottom: 6, borderRadius: 6,
                    backgroundColor: f.severity === "high" ? C.redBg : C.amberBg,
                    border: `1px solid ${f.severity === "high" ? C.redBorder : C.amberBorder}`,
                    fontSize: 12,
                  }}>
                    <div style={{ fontWeight: 600, color: f.severity === "high" ? C.red : C.amber }}>{f.title}</div>
                    <div style={{ color: C.textMuted, marginTop: 2 }}>{f.detail}</div>
                  </div>
                ))}
                {c.actionItems.length > 0 && (
                  <>
                    <SectionLabel>Open Action Items</SectionLabel>
                    {c.actionItems.map((a, i) => (
                      <div key={i} style={{ fontSize: 12, padding: "6px 0", color: C.textMuted }}>
                        <span style={{ color: C.red, fontWeight: 600 }}>{a.daysOverdue}d overdue</span>
                        {" — "}{a.desc} ({a.assignee})
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// ============================================================================
// ENGAGEMENT HEALTH TAB
// ============================================================================

function EngagementTab({ clients, selectedClient, setSelectedClient }) {
  const barData = clients.map((c) => ({
    name: c.name.replace("The ", "").replace(" Household", ""),
    score: c.engagementScore,
    aum: c.aum,
    fill: c.engagementScore >= 80 ? C.green : c.engagementScore >= 60 ? C.amber : C.red,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SectionLabel>Engagement Scores — All Clients</SectionLabel>

      <Card>
        <div style={{ height: 180 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: C.textMuted }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: C.textDim }} width={30} />
              <Tooltip formatter={(v) => [`${v}/100`, "Score"]}
                contentStyle={{ fontSize: 12, fontFamily: "'IBM Plex Mono', monospace", border: `1px solid ${C.border}`, borderRadius: 6 }} />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {barData.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Client engagement cards */}
      {clients.map((c) => {
        const isSelected = selectedClient === c.id;
        const riskColor = { low: C.green, moderate: C.amber, high: C.red, critical: C.red }[c.attritionRisk];

        return (
          <Card key={c.id} onClick={() => setSelectedClient(isSelected ? null : c.id)}
            style={{ borderColor: c.attritionRisk === "high" ? C.redBorder : C.border }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: "50%", display: "flex",
                  alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 700,
                  fontFamily: "'IBM Plex Mono', monospace",
                  backgroundColor: c.engagementScore >= 80 ? C.greenBg : c.engagementScore >= 60 ? C.amberBg : C.redBg,
                  color: c.engagementScore >= 80 ? C.green : c.engagementScore >= 60 ? C.amber : C.red,
                  border: `2px solid ${c.engagementScore >= 80 ? C.greenBorder : c.engagementScore >= 60 ? C.amberBorder : C.redBorder}`,
                }}>
                  {c.engagementScore}
                </div>
                <div>
                  <div style={{ fontWeight: 600 }}>{c.name}</div>
                  <div style={{ fontSize: 12, color: C.textMuted }}>
                    ${(c.aum / 1000).toFixed(0)}k — {c.advisor} — client since {c.clientSince}
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <Badge variant={c.engagementLevel}>{c.engagementLevel.replace("_", " ")}</Badge>
                <Badge variant={c.attritionRisk}>risk: {c.attritionRisk}</Badge>
              </div>
            </div>

            {/* Expanded: signal breakdown */}
            {isSelected && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                  <div>
                    <SectionLabel>Signal Breakdown</SectionLabel>
                    {c.signalScores.map((s, i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0" }}>
                        <span style={{ fontSize: 12, color: C.textMuted }}>{s.signal}</span>
                        <ScoreBar score={s.score} width={100} />
                      </div>
                    ))}
                  </div>
                  <div>
                    <SectionLabel>Engagement Radar</SectionLabel>
                    <EngagementRadar data={c.signalScores} />
                  </div>
                </div>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// ============================================================================
// CLIENT BRIEFING TAB
// ============================================================================

function BriefingTab({ clients, selectedClient, setSelectedClient }) {
  const client = selectedClient ? clients.find((c) => c.id === selectedClient) : null;

  return (
    <div>
      <SectionLabel>Select a Client</SectionLabel>
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {clients.map((c) => (
          <button key={c.id} onClick={() => setSelectedClient(c.id)} style={{
            padding: "8px 16px", borderRadius: 6, fontSize: 13, fontWeight: 500,
            border: `1px solid ${selectedClient === c.id ? C.text : C.border}`,
            backgroundColor: selectedClient === c.id ? C.text : C.surface,
            color: selectedClient === c.id ? C.surface : C.text,
            cursor: "pointer", fontFamily: "inherit",
          }}>
            {c.name.replace("The ", "").replace(" Household", "")}
            {c.flags.high > 0 && (
              <span style={{
                marginLeft: 6, fontSize: 10, fontWeight: 700, padding: "1px 5px",
                borderRadius: 8, backgroundColor: selectedClient === c.id ? C.red : C.redBg, color: selectedClient === c.id ? "#fff" : C.red,
              }}>{c.flags.high}</span>
            )}
          </button>
        ))}
      </div>

      {client && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Briefing Header */}
          <Card>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <h2 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 4px 0" }}>{client.name}</h2>
                <div style={{ fontSize: 13, color: C.textMuted }}>
                  {client.primary}{client.spouse ? ` & ${client.spouse}` : ""} — Client since {client.clientSince}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <Badge variant={client.tier}>{client.tier}</Badge>
                <Badge variant={client.reviewStatus}>{client.reviewStatus.replace("_", " ")}</Badge>
              </div>
            </div>
            <div style={{
              display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16,
              marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}`,
            }}>
              <Metric small value={`$${(client.aum / 1000).toFixed(0)}k`} label="AUM" />
              <Metric small value={`${client.aumChange >= 0 ? "+" : ""}${client.aumChange}%`} label="AUM Change" color={client.aumChange >= 0 ? C.green : C.red} />
              <Metric small value={`${client.performance.returnPct >= 0 ? "+" : ""}${client.performance.returnPct}%`} label="Return (Period)" color={client.performance.excessPct >= 0 ? C.green : C.red} />
              <Metric small value={client.engagementScore} label="Engagement" color={client.engagementScore >= 80 ? C.green : client.engagementScore >= 60 ? C.amber : C.red} />
            </div>
          </Card>

          {/* Flags */}
          {client.flags.items.length > 0 && (
            <Card>
              <SectionLabel>Attention Flags ({client.flags.high} high, {client.flags.medium} medium)</SectionLabel>
              {client.flags.items.map((f, i) => (
                <div key={i} style={{
                  padding: "10px 14px", marginBottom: 8, borderRadius: 6,
                  backgroundColor: f.severity === "high" ? C.redBg : C.amberBg,
                  border: `1px solid ${f.severity === "high" ? C.redBorder : C.amberBorder}`,
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: f.severity === "high" ? C.red : C.amber }}>{f.title}</div>
                  <div style={{ fontSize: 12, color: C.textMuted, marginTop: 2 }}>{f.detail}</div>
                </div>
              ))}
            </Card>
          )}

          {/* Conversation Starters */}
          <Card>
            <SectionLabel>Conversation Starters</SectionLabel>
            {client.conversationStarters.map((s, i) => (
              <div key={i} style={{
                padding: "10px 14px", marginBottom: 6, borderRadius: 6,
                backgroundColor: C.blueBg, border: `1px solid ${C.blueBorder}`, fontSize: 12, lineHeight: 1.5,
              }}>
                {s}
              </div>
            ))}
          </Card>

          {/* Action Items */}
          {client.actionItems.length > 0 && (
            <Card>
              <SectionLabel>Open Action Items</SectionLabel>
              {client.actionItems.map((a, i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "10px 0", borderBottom: i < client.actionItems.length - 1 ? `1px solid ${C.border}` : "none",
                }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{a.desc}</div>
                    <div style={{ fontSize: 11, color: C.textMuted }}>Assigned to {a.assignee}</div>
                  </div>
                  <Badge variant="overdue">{a.daysOverdue}d overdue</Badge>
                </div>
              ))}
            </Card>
          )}

          {/* Engagement Radar */}
          <Card>
            <SectionLabel>Engagement Signal Breakdown</SectionLabel>
            <EngagementRadar data={client.signalScores} />
          </Card>
        </div>
      )}

      {!client && (
        <Card style={{ textAlign: "center", padding: 40, color: C.textDim }}>
          Select a client above to view their review briefing.
        </Card>
      )}
    </div>
  );
}
