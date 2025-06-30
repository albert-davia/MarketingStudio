import operator

## Davia setup
## supabase setup
import os
from typing import Annotated, Any, Literal

from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command
from pydantic import BaseModel
from supabase import Client, create_client

supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

## LLM

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

## Tools

post_generation_prompt = """You are a world-class copywriter and content strategist.
Your job is to write high-performing content for:
{topic}
Details:
Target audience: {target_audience}
Platform: {platform}
Content type: {content_type}
Goal: {goal}
Instructions:
1. Start with a scroll-stopping hook
2. Use clear, concise, natural language
3. Apply storytelling, persuasion, and value delivery
4. Follow proven frameworks (AIDA, PAS, Hook-Point-Action, etc.)
5. End with a strong CTA
Write like a human. No fluff. No cringe. Make it hit.

Use the past posts as a reference to write the new post.

Past posts:
{past_posts}
"""

youtube_description_prompt = """You are a world-class YouTube content strategist and SEO expert.
Your job is to write high-performing YouTube video descriptions for:
{topic}
Details:
Target audience: {target_audience}
Video type: {content_type}
Goal: {goal}
Instructions:
1. Start with a compelling hook that matches the video title
2. Include relevant keywords naturally throughout the description
3. Provide a brief overview of what viewers will learn
4. Add timestamps if applicable
5. Include relevant links and resources
6. Use proper YouTube description formatting
7. End with a call-to-action for engagement (like, subscribe, comment)
8. Keep it under 5000 characters (YouTube limit)
9. Make it searchable and engaging

Use the past descriptions as a reference to write the new description.

Past descriptions:
{past_descriptions}
"""

goals = ["engagement", "clicks", "conversions", "leads"]

content_types = ["viral thread", "sales page", "cold email", "newsletter"]


class LinkedinPost(BaseModel):
    title: str
    post: str


class TwitterPost(BaseModel):
    post: str


class YouTubeDescription(BaseModel):
    title: str
    description: str
    video_url_drive: str


class State(MessagesState):
    linkedin_posts: Annotated[list[LinkedinPost], operator.add]
    new_linkedin_posts: Annotated[list[LinkedinPost], operator.add]
    twitter_posts: Annotated[list[TwitterPost], operator.add]
    new_twitter_posts: Annotated[list[TwitterPost], operator.add]
    youtube_descriptions: Annotated[list[YouTubeDescription], operator.add]
    new_youtube_descriptions: Annotated[list[YouTubeDescription], operator.add]


def write_linkedin_post(
    topic: str,
    target_audience: str,
    platform: str,
    content_type: str,
    goal: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Write a LinkedIn post about a given topic and post it"""
    post = model.with_structured_output(LinkedinPost).invoke(
        post_generation_prompt.format(
            topic=topic,
            target_audience=target_audience,
            platform=platform,
            content_type=content_type,
            goal=goal,
            past_posts=state["linkedin_posts"] + state["new_linkedin_posts"],
        )
    )
    return Command(
        update={
            "new_linkedin_posts": [post],
            "messages": [
                ToolMessage(
                    f"Linkedin post written: {post.title}",  # type: ignore
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


def write_twitter_post(
    topic: str,
    target_audience: str,
    platform: str,
    content_type: str,
    goal: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Write a Twitter post about a given topic and post it"""
    post = model.with_structured_output(TwitterPost).invoke(
        post_generation_prompt.format(
            topic=topic,
            target_audience=target_audience,
            platform=platform,
            content_type=content_type,
            goal=goal,
            past_posts=state["twitter_posts"] + state["new_twitter_posts"],
        )
    )
    return Command(
        update={
            "new_twitter_posts": [post],
            "messages": [
                ToolMessage(
                    f"Twitter post written: {post.post}",  # type: ignore
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


def write_youtube_description(
    topic: str,
    target_audience: str,
    content_type: str,
    goal: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Write a YouTube video description about a given topic and post it"""
    description = model.with_structured_output(YouTubeDescription).invoke(
        youtube_description_prompt.format(
            topic=topic,
            target_audience=target_audience,
            content_type=content_type,
            goal=goal,
            past_descriptions=state["youtube_descriptions"],
        )
    )
    return Command(
        update={
            "youtube_descriptions": [description],
            "messages": [
                ToolMessage(
                    f"YouTube description written: {description.title}",  # type: ignore
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


agent_prompt = """ You are a world-class content strategist, you lead a team of copywrites.
You work for a company Davia that sells a product called "Davia". It is a tool that helps people build front end for their applications.
The goal of the company is to allow builders to build powerful AI applications without coding or using their existing python backend.
You need to maintain the company's social media presence and create content for the company's social media accounts.
Your goal is to post videos on Youtube, post on Linkedin and Twitter, at least once every two days.
You conduct weekly check-ins with the team to discuss posts for the next week.

Use the following tools to help you:
- write_linkedin_post
- write_twitter_post
- write_youtube_description

Never use the tools if you don't have to.
Never try to do something yourself if you can use the tools.
"""

tools = [write_linkedin_post, write_twitter_post, write_youtube_description]

model_with_tools = model.bind_tools(tools)


def agent(state: State):
    return {"messages": [model_with_tools.invoke([agent_prompt] + state["messages"])]}


def load_state(state: State):
    return {
        "linkedin_posts": supabase.table("linkedin_posts").select("*").execute().data,
        # "twitter_posts": supabase.table("twitter_posts").select("*").execute().data,
        # "youtube_descriptions": supabase.table("youtube_descriptions")
        # .select("*")
        # .execute()
        # .data,
    }


def save_state(state: State):
    if state.get("new_linkedin_posts"):
        data = [p.model_dump() for p in state["new_linkedin_posts"]]
        supabase.table("linkedin_posts").insert(data).execute()
    if state.get("new_twitter_posts"):
        data = [p.model_dump() for p in state["new_twitter_posts"]]
        supabase.table("twitter_posts").insert(data).execute()
    # supabase.table("youtube_descriptions").insert(
    #     state["youtube_descriptions"]
    # ).execute()


def custom_tools_condition(
    state: list[AnyMessage] | dict[str, Any] | BaseModel,
    messages_key: str = "messages",
) -> Literal["tools", "save_state"]:
    """Use in the conditional_edge to route to the ToolNode if the last message

    has tool calls. Otherwise, route to the end.

    Args:
        state (Union[list[AnyMessage], dict[str, Any], BaseModel]): The state to check for
            tool calls. Must have a list of messages (MessageGraph) or have the
            "messages" key (StateGraph).

    Returns:
        The next node to route to.


    Examples:
        Create a custom ReAct-style agent with tools.

        ```pycon
        >>> from langchain_anthropic import ChatAnthropic
        >>> from langchain_core.tools import tool
        ...
        >>> from langgraph.graph import StateGraph
        >>> from langgraph.prebuilt import ToolNode, tools_condition
        >>> from langgraph.graph.message import add_messages
        ...
        >>> from typing import Annotated
        >>> from typing_extensions import TypedDict
        ...
        >>> @tool
        >>> def divide(a: float, b: float) -> int:
        ...     \"\"\"Return a / b.\"\"\"
        ...     return a / b
        ...
        >>> llm = ChatAnthropic(model="claude-3-haiku-20240307")
        >>> tools = [divide]
        ...
        >>> class State(TypedDict):
        ...     messages: Annotated[list, add_messages]
        >>>
        >>> graph_builder = StateGraph(State)
        >>> graph_builder.add_node("tools", ToolNode(tools))
        >>> graph_builder.add_node("chatbot", lambda state: {"messages":llm.bind_tools(tools).invoke(state['messages'])})
        >>> graph_builder.add_edge("tools", "chatbot")
        >>> graph_builder.add_conditional_edges(
        ...     "chatbot", tools_condition
        ... )
        >>> graph_builder.set_entry_point("chatbot")
        >>> graph = graph_builder.compile()
        >>> graph.invoke({"messages": {"role": "user", "content": "What's 329993 divided by 13662?"}})
        ```
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif isinstance(state, dict) and (messages := state.get(messages_key, [])):
        ai_message = messages[-1]
    elif messages := getattr(state, messages_key, []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:  # type: ignore
        return "tools"
    return "save_state"


graph = StateGraph(State)

graph.add_node("agent", agent)

graph.add_node("load_state", load_state)

graph.add_node("tools", ToolNode(tools=tools))

graph.add_node("save_state", save_state)

graph.add_edge("__start__", "load_state")

graph.add_edge("load_state", "agent")

graph.add_edge("tools", "agent")

graph.add_edge("save_state", "__end__")

graph.add_conditional_edges("agent", custom_tools_condition)

graph.compile()
