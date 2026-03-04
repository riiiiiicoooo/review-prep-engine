"""
Review Prep Engine - MCP Server
Model Context Protocol implementation for generating client review briefings,
fetching client summaries, and searching advisor notes. Supports various
review types: quarterly, annual, comprehensive, etc.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging

from mcp.server import Server, Tool
from mcp.types import TextContent

# Data access
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP Server
server = Server("review-prep-engine")


class BriefingGenerator:
    """Generate formatted review briefings for clients."""
    
    REVIEW_TYPES = [
        "quarterly",
        "annual", 
        "comprehensive",
        "performance",
        "risk",
        "planning",
    ]
    
    def __init__(self, briefing_api_url: str, api_key: str):
        self.briefing_api_url = briefing_api_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
    async def generate_briefing(
        self,
        client_id: str,
        review_type: str,
        custom_sections: Optional[List[str]] = None,
    ) -> str:
        """
        Generate review briefing document for client.
        
        Review types:
        - quarterly: Recent performance metrics and activities
        - annual: Year-over-year comparison, goals review
        - comprehensive: Complete portfolio analysis and recommendations
        - performance: Detailed performance vs. benchmarks
        - risk: Risk assessment and mitigation strategies
        - planning: Strategic planning and goal-setting
        
        Returns markdown-formatted briefing.
        """
        try:
            payload = {
                "client_id": client_id,
                "review_type": review_type,
                "custom_sections": custom_sections or [],
            }
            
            response = await self.client.post(
                f"{self.briefing_api_url}/briefings/generate",
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("markdown_content", "")
        except Exception as e:
            logger.error(f"Briefing generation failed: {str(e)}")
            raise


class ClientSummaryProvider:
    """Provide client overviews and key metrics."""
    
    def __init__(self, client_api_url: str, api_key: str):
        self.client_api_url = client_api_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
    async def get_client_summary(self, client_id: str) -> Dict[str, Any]:
        """
        Get comprehensive client summary with metrics.
        
        Returns:
        - Client profile (name, type, contact, relationship)
        - Assets under management (AUM)
        - Performance metrics (return, volatility, Sharpe ratio)
        - Holdings summary (top 10 positions, sector allocation)
        - Goals and constraints
        - Review history
        """
        try:
            response = await self.client.get(
                f"{self.client_api_url}/clients/{client_id}/summary"
            )
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Client summary retrieval failed: {str(e)}")
            raise


class NotesSearchEngine:
    """Search across advisor notes and meeting records."""
    
    def __init__(self, notes_api_url: str, api_key: str):
        self.notes_api_url = notes_api_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
    async def search_notes(
        self,
        query: str,
        client_id: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
        note_types: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across advisor notes and meeting records.
        
        Returns relevant notes ranked by relevance.
        """
        try:
            params = {
                "query": query,
                "top_k": min(top_k, 50),
            }
            
            if client_id:
                params["client_id"] = client_id
            
            if date_range:
                params["start_date"] = date_range.get("start")
                params["end_date"] = date_range.get("end")
            
            if note_types:
                params["note_types"] = note_types
            
            response = await self.client.get(
                f"{self.notes_api_url}/notes/search",
                params=params,
            )
            response.raise_for_status()
            
            results = response.json().get("results", [])
            return results
        except Exception as e:
            logger.error(f"Notes search failed: {str(e)}")
            return []


# Global clients
briefing_gen = None
client_provider = None
notes_engine = None


@server.list_tools()
def list_tools():
    """Register all review prep tools."""
    return [
        Tool(
            name="generate_briefing",
            description=(
                "Generate a formatted review briefing for a client meeting. "
                "Supports multiple review types (quarterly, annual, comprehensive, etc.). "
                "Returns markdown ready for presentation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Client identifier",
                    },
                    "review_type": {
                        "type": "string",
                        "enum": [
                            "quarterly",
                            "annual",
                            "comprehensive",
                            "performance",
                            "risk",
                            "planning",
                        ],
                        "description": "Type of review to prepare",
                    },
                    "custom_sections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: custom sections to include (e.g., ['tax_planning', 'estate_goals', 'charitable_giving'])",
                    },
                    "tenant_id": {
                        "type": "string",
                        "description": "Tenant identifier",
                    },
                },
                "required": ["client_id", "review_type", "tenant_id"],
            },
        ),
        Tool(
            name="get_client_summary",
            description=(
                "Get comprehensive client overview with key metrics. "
                "Includes profile, assets, performance, holdings, and goals."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Client identifier",
                    },
                    "tenant_id": {
                        "type": "string",
                        "description": "Tenant identifier",
                    },
                },
                "required": ["client_id", "tenant_id"],
            },
        ),
        Tool(
            name="search_notes",
            description=(
                "Search across advisor notes and meeting records using natural language. "
                "Find relevant notes by topic, date, or note type."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query (e.g., 'tax loss harvesting' or 'Roth conversion discussion')",
                    },
                    "client_id": {
                        "type": "string",
                        "description": "Optional: filter to specific client",
                    },
                    "date_range": {
                        "type": "object",
                        "properties": {
                            "start": {
                                "type": "string",
                                "description": "Start date (YYYY-MM-DD)",
                            },
                            "end": {
                                "type": "string",
                                "description": "End date (YYYY-MM-DD)",
                            },
                        },
                        "description": "Optional: filter by date range",
                    },
                    "note_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: filter by note type (e.g., ['meeting', 'phone_call', 'email', 'internal_note'])",
                    },
                    "tenant_id": {
                        "type": "string",
                        "description": "Tenant identifier",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results (default: 10, max: 50)",
                        "default": 10,
                    },
                },
                "required": ["query", "tenant_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool invocations."""
    
    if name == "generate_briefing":
        return await _generate_briefing(arguments)
    elif name == "get_client_summary":
        return await _get_client_summary(arguments)
    elif name == "search_notes":
        return await _search_notes(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def _generate_briefing(args: Dict[str, Any]) -> List[TextContent]:
    """Generate review briefing."""
    try:
        client_id = args["client_id"]
        review_type = args["review_type"]
        custom_sections = args.get("custom_sections", [])
        
        markdown = await briefing_gen.generate_briefing(
            client_id, review_type, custom_sections
        )
        
        return [
            TextContent(
                type="text",
                text=json.dumps({
                    "client_id": client_id,
                    "review_type": review_type,
                    "briefing": markdown,
                    "timestamp": datetime.utcnow().isoformat(),
                }, indent=2),
            )
        ]
    except Exception as e:
        logger.error(f"Briefing generation failed: {str(e)}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _get_client_summary(args: Dict[str, Any]) -> List[TextContent]:
    """Get client summary."""
    try:
        client_id = args["client_id"]
        
        summary = await client_provider.get_client_summary(client_id)
        
        return [TextContent(type="text", text=json.dumps(summary, indent=2, default=str))]
    except Exception as e:
        logger.error(f"Client summary retrieval failed: {str(e)}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _search_notes(args: Dict[str, Any]) -> List[TextContent]:
    """Search notes."""
    try:
        results = await notes_engine.search_notes(
            query=args["query"],
            client_id=args.get("client_id"),
            date_range=args.get("date_range"),
            note_types=args.get("note_types"),
            top_k=args.get("top_k", 10),
        )
        
        return [
            TextContent(
                type="text",
                text=json.dumps({
                    "query": args["query"],
                    "result_count": len(results),
                    "results": results,
                    "timestamp": datetime.utcnow().isoformat(),
                }, indent=2),
            )
        ]
    except Exception as e:
        logger.error(f"Notes search failed: {str(e)}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


def initialize_mcp_server():
    """Initialize review prep clients."""
    global briefing_gen, client_provider, notes_engine
    
    api_url = os.getenv("REVIEW_PREP_API_URL", "http://localhost:8000")
    api_key = os.getenv("API_KEY", "")
    
    briefing_gen = BriefingGenerator(api_url, api_key)
    client_provider = ClientSummaryProvider(api_url, api_key)
    notes_engine = NotesSearchEngine(api_url, api_key)
    
    logger.info("Review Prep Engine MCP server initialized")


if __name__ == "__main__":
    initialize_mcp_server()
    server.run()
