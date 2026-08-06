"""SQLAgent Orchestration Service.

Handles model tool invocation loop, memory contexts injection,
and runtime execution workflows.
"""

import os
import json
import time
import logging
from typing import List, Dict, Any, Optional

from agent.memory import ConversationMemoryManager
from agent.registry import ToolRegistry
from agent.state import AgentState, StateMachine
from agent.planner import QueryPlanner
from agent.tool_executor import ToolExecutor
from services.groq_service import GroqService
from core.database import DatabaseManager
from models.models import AgentResponse, ToolResponse, ExecutionMetrics
from config import settings

logger = logging.getLogger("agent.orchestrator")

class SQLAgent:
    """Autonomous agent coordinating natural language queries to SQL workflows."""
    
    def __init__(self, db_path: str, model_name: Optional[str] = None):
        """Initializes the agent.
        
        Args:
            db_path: Path to target database file.
            model_name: Optional name of the LLM to run.
        """
        self.db_path = os.path.abspath(db_path)
        self.model_name = model_name if model_name is not None else settings.LLM_MODEL
        self.memory = ConversationMemoryManager()
        self.registry = ToolRegistry()
        self._register_default_tools()
        
    def _register_default_tools(self) -> None:
        """Registers default agent tools with the registry."""
        from tools.list_tables import ListTablesTool
        from tools.get_schema import GetSchemaTool
        from tools.run_query import RunQueryTool
        from tools.get_sample_rows import GetSampleRowsTool
        from tools.find_column_values import FindColumnValuesTool
        from tools.validate_sql import ValidateSqlTool
        from tools.sanitize_sql import SanitizeSqlTool
        from tools.explain_query import ExplainQueryTool
        from tools.suggest_indexes import SuggestIndexesTool

        self.registry.register(ListTablesTool(self.db_path))
        self.registry.register(GetSchemaTool(self.db_path))
        self.registry.register(RunQueryTool(self.db_path))
        self.registry.register(GetSampleRowsTool(self.db_path))
        self.registry.register(FindColumnValuesTool(self.db_path))
        self.registry.register(ValidateSqlTool(self.db_path))
        self.registry.register(SanitizeSqlTool(self.db_path))
        self.registry.register(ExplainQueryTool(self.db_path))
        self.registry.register(SuggestIndexesTool(self.db_path))

    def execute(self, user_query: str) -> AgentResponse:
        """Runs agent orchestration execution loop.
        
        Args:
            user_query: Plain text natural language question.
            
        Returns:
            Structured AgentResponse object.
        """
        start_time = time.perf_counter()
        
        state_machine = StateMachine(AgentState.IDLE)
        state_machine.transition_to(AgentState.UNDERSTAND)
        
        logger.info(f"Agent starting execution for user query: '{user_query}'")
        
        # Initialize execution metrics
        llm_latency_ms = 0.0
        tool_latency_ms = 0.0
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        tool_calls_count = 0
        retries_count = 0
        
        # Load system prompts if memory is empty
        if not self.memory.messages:
            system_prompt_path = os.path.join("prompts", "system_prompt.txt")
            sql_rules_path = os.path.join("prompts", "sql_rules.txt")
            
            system_content = "You are an expert AI Data Analyst.\nYour goal is to answer the user's question by inspecting the database schema, selecting appropriate tables, and generating correct SQLite queries.\nYou must use your registered tools. Do not assume database structures. Always query get_schema."
            sql_rules_content = "SQLite Dialect Rules:\n- Only select read-only syntax structures.\n- Enclose column references containing spaces in double quotes.\n- Cast all raw outputs calculations.\n- Enforce LIMIT clauses to protect memory targets."
            
            try:
                if os.path.exists(system_prompt_path):
                    with open(system_prompt_path, "r", encoding="utf-8") as f:
                        system_content = f.read()
                if os.path.exists(sql_rules_path):
                    with open(sql_rules_path, "r", encoding="utf-8") as f:
                        sql_rules_content = f.read()
            except Exception:
                pass
                
            self.memory.add_message("system", system_content)
            self.memory.add_message("system", sql_rules_content)
            
            # Load dynamic schema cached context
            try:
                db_mgr = DatabaseManager(self.db_path)
                tables = db_mgr.get_table_list()
                schema_parts = []
                for table in tables:
                    meta = db_mgr.get_schema_metadata(table)
                    cols_str = ", ".join([f"{c['name']} ({c['type']})" for c in meta["columns"]])
                    schema_parts.append(f"Table: {table}\nColumns: {cols_str}")
                schema_context = "Database Schema Context:\n" + "\n\n".join(schema_parts)
                self.memory.add_message("system", schema_context)
            except Exception as e:
                self.memory.add_message("system", f"Database Schema Context could not be retrieved: {e}")
        
        # Add user query to memory
        self.memory.add_message("user", user_query)
        
        # Transition state to PLAN and run query planner
        state_machine.transition_to(AgentState.PLAN)
        category = QueryPlanner.classify_question(user_query)
        allowed_tools = QueryPlanner.plan_tools(category)
        logger.info(f"Planned tools for classification '{category}': {allowed_tools}")
        
        max_cycles = 5
        steps = []
        sql_query_executed = None
        
        groq_service = GroqService()
        tool_executor = ToolExecutor(self.registry)
        
        for cycle in range(max_cycles):
            messages = self.memory.get_history_within_tokens()
            # Restrict tool schemas to those allowed by the planner
            all_schemas = self.registry.get_all_schemas()
            tools_schema = [s for s in all_schemas if s["function"]["name"] in allowed_tools]
            
            state_machine.transition_to(AgentState.CALL_TOOL)
            
            llm_start = time.perf_counter()
            try:
                message = groq_service.generate_completion(messages, tools=tools_schema)
                llm_latency_ms += (time.perf_counter() - llm_start) * 1000.0
            except Exception as e:
                state_machine.transition_to(AgentState.FINISHED)
                logger.error(f"LLM API completion failed: {e}")
                return AgentResponse(
                    response_text=f"Failed to generate response: {e}",
                    steps=steps,
                    metrics=ExecutionMetrics(
                        total_duration_ms=(time.perf_counter() - start_time) * 1000.0,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens
                    )
                )
                
            # Accumulate estimated token counts
            prompt_tokens += sum(self.memory._count_tokens(m) for m in messages)
            completion_tokens += self.memory._count_tokens({"role": "assistant", "content": message.content or ""})
            total_tokens = prompt_tokens + completion_tokens
            
            tool_calls = getattr(message, "tool_calls", None)
            
            if tool_calls:
                state_machine.transition_to(AgentState.WAIT_TOOL)
                
                assistant_content = message.content or ""
                msg_dict = {
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in tool_calls
                    ]
                }
                self.memory.messages.append(msg_dict)
                
                for tc in tool_calls:
                    tool_calls_count += 1
                    name = tc.function.name
                    args_str = tc.function.arguments
                    try:
                        args = json.loads(args_str)
                    except Exception:
                        args = {}
                        
                    step_start = time.perf_counter()
                    tool_resp = tool_executor.execute_single(name, args)
                    step_duration = (time.perf_counter() - step_start) * 1000.0
                    tool_latency_ms += step_duration
                    
                    # Capture SQL execution failure for self-correction retries
                    if name == "run_query" and not tool_resp.is_success:
                        retries_count += 1
                        logger.warning(f"SQL execution failed: {tool_resp.result_content}. Self-correction attempt: {retries_count}/{settings.MAX_RETRIES}")
                        if retries_count > settings.MAX_RETRIES:
                            logger.error("SQL Self-Correction limit exceeded.")
                            tool_resp.result_content = f"Error: SQL query failed too many times. Final error: {tool_resp.result_content}"
                            
                    steps.append({
                        "step": len(steps) + 1,
                        "tool_called": name,
                        "arguments": args_str,
                        "duration_ms": step_duration,
                        "status": "SUCCESS" if tool_resp.is_success else "FAILED",
                        "result": tool_resp.result_content
                    })
                    
                    if name == "run_query" and "sql" in args:
                        sql_query_executed = args["sql"]
                        
                    self.memory.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": name,
                        "content": tool_resp.result_content
                    })
                    
                state_machine.transition_to(AgentState.PROCESS_RESULT)
            else:
                state_machine.transition_to(AgentState.GENERATE_FINAL_RESPONSE)
                self.memory.add_message("assistant", message.content or "")
                state_machine.transition_to(AgentState.FINISHED)
                
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                
                logger.info(f"Agent finished reasoning loop successfully. Output: '{message.content[:60]}...'")
                
                return AgentResponse(
                    response_text=message.content or "",
                    sql_query=sql_query_executed,
                    steps=steps,
                    metrics=ExecutionMetrics(
                        total_duration_ms=duration_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens
                    )
                )
                
        # Fallback completion
        state_machine.transition_to(AgentState.GENERATE_FINAL_RESPONSE)
        messages = self.memory.get_history_within_tokens()
        try:
            message = groq_service.generate_completion(messages)
            self.memory.add_message("assistant", message.content or "")
            resp_text = message.content or ""
        except Exception as e:
            resp_text = f"Agent completed cycles loop. Final generation error: {e}"
            
        state_machine.transition_to(AgentState.FINISHED)
        
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return AgentResponse(
            response_text=resp_text,
            sql_query=sql_query_executed,
            steps=steps,
            metrics=ExecutionMetrics(
                total_duration_ms=duration_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
        )
