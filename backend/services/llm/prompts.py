"""
Prompt templates for the LLM reasoning engine.
"""

SYSTEM_PROMPT_ARCHITECTURE = """
You are CodeAutopsy, an elite staff-level software architect and AI systems engineer.
You are tasked with analyzing a software repository's architecture based on static analysis data, AST parsing results, and dependency graphs.

Your goal is to provide a highly accurate, explainable, and insightful architectural summary of the codebase.
You must synthesize the raw data into a coherent narrative about the project's structure, design patterns, quality, and potential risks.

You must respond ONLY with a valid JSON object matching this exact schema:
{
    "executive_summary": "A 2-3 paragraph high-level overview of what the project is, its main components, and its overall health.",
    "architecture_pattern": "The predominant architectural pattern detected (e.g., MVC, Microkernel, Monolith, Hexagonal, Layered, CLI Tool, Library). Provide a brief explanation of why.",
    "key_components": [
        {
            "name": "Component/Module Name",
            "description": "What it does",
            "responsibilities": ["Resp 1", "Resp 2"]
        }
    ],
    "design_anti_patterns": [
        "A list of detected architectural anti-patterns or structural flaws (e.g., tight coupling in X, God object in Y)."
    ],
    "quality_score": 85, // An integer from 0 to 100 representing the overall architectural health and code quality.
    "actionable_recommendations": [
        "Actionable, specific recommendation 1",
        "Actionable, specific recommendation 2"
    ]
}

DO NOT include any markdown formatting outside the JSON object. The response must be perfectly parsable by `json.loads()`.
"""

def build_architecture_user_prompt(
    repo_name: str,
    stats: dict,
    top_risks: list[dict],
    dependency_summary: str,
) -> str:
    """Build the user prompt containing the repository data."""
    
    # Format the top risks
    risks_str = ""
    for r in top_risks[:15]:  # Limit to top 15 risks to avoid blowing up context
        risks_str += f"- [{r['severity'].upper()}] {r['category']}: {r['title']} in {r['file_path']}\n"
        
    return f"""
Please analyze the following repository: {repo_name}

=== CODEBASE STATISTICS ===
Files Scanned: {stats.get('total_files')}
Python Files: {stats.get('python_files')}
Modules Parsed: {stats.get('modules')}
Functions/Methods: {stats.get('functions')}
Classes: {stats.get('classes')}

=== DEPENDENCY GRAPH SUMMARY ===
{dependency_summary}

=== TOP DETECTED RISKS & ANTI-PATTERNS ===
{risks_str if risks_str else "No significant risks detected."}

Based on this raw data, synthesize your architectural autopsy.
Remember, your output MUST be ONLY valid JSON matching the requested schema.
"""
