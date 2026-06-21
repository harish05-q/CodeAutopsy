export type ViewId = "overview" | "dependencies" | "calls" | "architecture" | "onboarding" | "risks" | "chat";

export const navItems: { id: ViewId; label: string; index: string }[] = [
  { id: "overview", label: "Field notes", index: "01" },
  { id: "dependencies", label: "Dependencies", index: "02" },
  { id: "calls", label: "Call anatomy", index: "03" },
  { id: "architecture", label: "Architecture", index: "04" },
  { id: "onboarding", label: "Onboarding", index: "05" },
  { id: "risks", label: "Risk tissue", index: "06" },
  { id: "chat", label: "Ask the code", index: "07" },
];

export const stats = [
  { value: "2,418", label: "Files", note: "+184 tests" },
  { value: "126", label: "Modules", note: "12 core" },
  { value: "84", label: "Classes", note: "6 abstract" },
  { value: "1,093", label: "Functions", note: "71% typed" },
];

export const hotspots = [
  { file: "services/auth/session.py", risk: "High", score: 91, color: "#e85d3f" },
  { file: "api/v1/repositories.py", risk: "Medium", score: 68, color: "#ed9d58" },
  { file: "agents/graph_agent.py", risk: "Medium", score: 57, color: "#d8bc4c" },
];

export const activity = [
  ["AST extraction", "2,418 files mapped", "00:42"],
  ["Architecture inference", "Layered monolith · 87%", "01:18"],
  ["Semantic index", "8,604 chunks embedded", "02:07"],
  ["Risk analysis", "14 hotspots isolated", "02:31"],
];

export const importantFiles = [
  ["backend/main.py", "Application entry", "Start here"],
  ["backend/core/config.py", "Runtime configuration", "4 min"],
  ["backend/api/routes.py", "HTTP surface", "8 min"],
  ["backend/agents/orchestrator.py", "Analysis pipeline", "12 min"],
  ["frontend/lib/api.ts", "Client boundary", "5 min"],
];
