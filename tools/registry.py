"""MCP Tool Registry — maps tool names to Python callables."""
from __future__ import annotations
from typing import Any, Callable, Dict
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._register_defaults()

    def _register_defaults(self):
        import shlex
        import subprocess

        try:
            from tools.file_io import file_write, file_read
            self.register("file_write",  file_write)
            self.register("file_read",   file_read)
        except ImportError:
            pass

        try:
            from tools.linter import run_linter
            self.register("run_linter", run_linter)
        except ImportError:
            pass

        self.register("run_command", lambda cmd: subprocess.run(
            cmd, capture_output=True, text=True,
            check=True, timeout=60, shell=True))
        
        self._register_optional_tools()

    def _register_optional_tools(self):
        # Email sender
        try:
            from tools.email_sender import send_email
            self.register("send_email", send_email)
            logger.info("Registered tool: send_email")
        except ImportError as e:
            logger.debug(f"send_email not available: {e}")

        # API integrations
        try:
            from tools.news_client import fetch_news
            self.register("fetch_news", fetch_news)
            logger.info("Registered tool: fetch_news")
        except ImportError as e:
            logger.debug(f"fetch_news not available: {e}")

        try:
            from tools.news_api_client import get_news, NewsAPIClient, GNewsClient
            self.register("get_news", get_news)
            na = NewsAPIClient()
            if na.key:
                self.register("newsapi_headlines",
                             lambda **kw: na.top_headlines(**kw))
            gn = GNewsClient()
            if gn.key:
                self.register("gnews_headlines",
                             lambda **kw: gn.top_headlines(**kw))
            logger.info("Registered tools: get_news, newsapi_*, gnews_*")
        except ImportError as e:
            logger.debug(f"news_api_client not available: {e}")

        try:
            from tools.market_data import MarketDataClient
            mdc = MarketDataClient()
            self.register("market_summary", mdc.market_summary)
            self.register("crypto_prices", mdc.crypto_prices)
            self.register("stock_prices", mdc.stock_prices)
            logger.info("Registered tools: market_*")
        except ImportError as e:
            logger.debug(f"market_data not available: {e}")

        try:
            from tools.odds_client import fetch_odds
            self.register("fetch_odds", fetch_odds)
            logger.info("Registered tool: fetch_odds")
        except ImportError as e:
            logger.debug(f"fetch_odds not available: {e}")

        try:
            from tools.free_api_clients import (
                CoinGeckoClient, OpenMeteoClient, OddsAPIClient,
                AlphaVantageClient, get_market_data,
            )
            cg = CoinGeckoClient()
            self.register("crypto_trending", cg.trending)
            self.register("crypto_price", cg.price)
            self.register("crypto_top", cg.top_coins)
            om = OpenMeteoClient()
            self.register("weather_forecast", om.forecast)
            self.register("weather_current", om.current)
            oa = OddsAPIClient()
            if oa.key:
                self.register("odds_sports", oa.sports)
                self.register("odds_fetch", oa.odds)
            av = AlphaVantageClient()
            if av.key:
                self.register("stock_quote", av.quote)
                self.register("stock_daily", av.daily)
            self.register("market_data_agg", get_market_data)
            logger.info("Registered tools: crypto_*, weather_*, odds_*, stock_*")
        except ImportError as e:
            logger.debug(f"free_api_clients not available: {e}")

        try:
            from tools.finance_client import StripeClient, CoinbaseClient
            sc = StripeClient()
            if sc.client.api_key:
                self.register("stripe_customers", sc.list_customers)
                self.register("stripe_subscriptions", sc.list_subscriptions)
                self.register("stripe_balance", sc.balance)
            cb = CoinbaseClient()
            self.register("coinbase_spot", cb.spot_price)
            self.register("coinbase_rates", cb.exchange_rates)
            logger.info("Registered tools: stripe_*, coinbase_*")
        except ImportError as e:
            logger.debug(f"finance_client not available: {e}")

        try:
            from tools.free_api_clients import (
                FrankfurterClient, HackerNewsClient, WikipediaClient,
                DatamuseClient, JokeAPIClient, NumbersAPIClient,
                get_free_dashboard,
            )
            ff = FrankfurterClient()
            self.register("exchange_latest", ff.latest)
            self.register("exchange_currencies", ff.currencies)
            hn = HackerNewsClient()
            self.register("hn_top", hn.top_stories)
            self.register("hn_best", hn.best_stories)
            self.register("hn_new", hn.new_stories)
            wp = WikipediaClient()
            self.register("wiki_summary", wp.summary)
            self.register("wiki_onthisday", wp.on_this_day)
            dm = DatamuseClient()
            self.register("word_rhymes", dm.rhymes)
            self.register("word_synonyms", dm.synonyms)
            jk = JokeAPIClient()
            self.register("get_joke", jk.get)
            nm = NumbersAPIClient()
            self.register("number_fact", nm.fact)
            self.register("free_dashboard", get_free_dashboard)
            logger.info("Registered tools: exchange_*, hn_*, wiki_*, word_*, joke_*")
        except ImportError as e:
            logger.debug(f"free_api_clients (extended) not available: {e}")

        try:
            from tools.more_free_apis import (
                ArxivClient, RedditClient, DevToClient,
                ProductHuntClient, TechFeedClient, get_tech_dashboard,
            )
            ax = ArxivClient()
            self.register("arxiv_search", ax.search)
            self.register("arxiv_latest", ax.latest_in)
            rd = RedditClient()
            self.register("reddit_hot", rd.hot)
            self.register("reddit_top", rd.top)
            dv = DevToClient()
            self.register("devto_top", dv.top_articles)
            self.register("devto_tag", dv.by_tag)
            ph = ProductHuntClient()
            self.register("producthunt_trending", ph.trending)
            tf = TechFeedClient()
            self.register("tech_feeds", tf.fetch)
            self.register("tech_dashboard", get_tech_dashboard)
            logger.info("Registered tools: arxiv_*, reddit_*, devto_*, producthunt_*, tech_*")
        except ImportError as e:
            logger.debug(f"more_free_apis not available: {e}")

        try:
            from features.social_posting import SocialPoster, quick_post, crosspost
            self.register("social_post", quick_post)
            self.register("social_crosspost", crosspost)
            logger.info("Registered tools: social_post, social_crosspost")
        except ImportError as e:
            logger.debug(f"social_posting not available: {e}")

        try:
            from tools.google_client import GoogleClient, google_status
            gc = GoogleClient()
            if gc.maps_key:
                self.register("google_geocode", gc.geocode)
                self.register("google_places", gc.places_search)
            if gc.youtube_key:
                self.register("youtube_search", gc.youtube_search)
            if gc.calendar_id and gc.maps_key:
                self.register("google_calendar", gc.calendar_events)
            if gc.email and gc.app_password:
                self.register("gmail_send", gc.send_email)
            self.register("google_status", google_status)
            logger.info("Registered tools: google_*, youtube_*, gmail_*")
        except ImportError as e:
            logger.debug(f"google_client not available: {e}")

        try:
            from tools.research_clients import GeminiClient, PerplexityClient, deep_research
            gm = GeminiClient()
            if gm.key:
                self.register("gemini_research", gm.research)
                self.register("gemini_summarize", gm.summarize)
                self.register("gemini_analyze", gm.analyze)
                self.register("gemini_brainstorm", gm.brainstorm)
                self.register("gemini_quick", gm.quick_answer)
            self.register("deep_research", deep_research)
            logger.info("Registered tools: gemini_*, deep_research")
        except ImportError as e:
            logger.debug(f"research_clients not available: {e}")

        try:
            from tools.ollama_client import OllamaClient, get_ollama
            oc = get_ollama()
            self.register("ollama_chat", oc.chat)
            self.register("ollama_scaffold", oc.scaffold)
            self.register("ollama_quick_code", oc.quick_code)
            self.register("ollama_explain", oc.explain)
            self.register("ollama_models", oc.models)
            self.register("ollama_status", oc.status)
            logger.info("Registered tools: ollama_*")
        except ImportError as e:
            logger.debug(f"ollama_client not available: {e}")

        try:
            from tools.litellm_proxy import LiteLLMRouter
            router = LiteLLMRouter()
            self.register("llm_complete", router.complete)
            self.register("llm_chat", router.chat)
            self.register("llm_status", router.status)
            logger.info("Registered tools: llm_complete, llm_chat, llm_status")
        except ImportError as e:
            logger.debug(f"litellm_proxy not available: {e}")

        try:
            from tools.github_client import GitHubClient
            gh = GitHubClient()
            self.register("github_list_issues", gh.list_issues)
            self.register("github_create_issue", gh.create_issue)
            self.register("github_search_code", gh.search_code)
            logger.info("Registered tools: github_*")
        except ImportError as e:
            logger.debug(f"github_client not available: {e}")

        try:
            from tools.cloudflare_client import CloudflareClient
            cf = CloudflareClient()
            self.register("cloudflare_deploy", cf.deploy_pages)
            self.register("cloudflare_purge", cf.purge_cache)
            logger.info("Registered tools: cloudflare_*")
        except ImportError as e:
            logger.debug(f"cloudflare_client not available: {e}")

        try:
            from lanes.monte_carlo_bettor import MonteCarloBettor
            mcb = MonteCarloBettor(simulations=5000)
            self.register("monte_carlo_bet", mcb.simulate)
            logger.info("Registered tool: monte_carlo_bet")
        except ImportError as e:
            logger.debug(f"monte_carlo_bettor not available: {e}")

        try:
            from tools.webhook_dispatcher import WebhookDispatcher
            wh = WebhookDispatcher()
            self.register("slack_notify", wh.slack)
            self.register("discord_notify", wh.discord)
            self.register("notify_skill_result", wh.notify_skill_result)
            logger.info("Registered tools: slack_notify, discord_notify, notify_skill_result")
        except ImportError as e:
            logger.debug(f"webhook_dispatcher not available: {e}")

        try:
            from tools.gitlab_client import GitLabClient
            gl = GitLabClient()
            self.register("gitlab_list_issues", gl.list_issues)
            self.register("gitlab_create_issue", gl.create_issue)
            self.register("gitlab_list_mrs", gl.list_merge_requests)
            logger.info("Registered tools: gitlab_*")
        except ImportError as e:
            logger.debug(f"gitlab_client not available: {e}")

        try:
            from tools.linear_jira_client import LinearClient
            lc = LinearClient()
            self.register("linear_list_issues", lc.list_issues)
            self.register("linear_create_issue", lc.create_issue)
            self.register("linear_search", lc.search_issues)
            logger.info("Registered tools: linear_*")
        except ImportError as e:
            logger.debug(f"linear_client not available: {e}")

        try:
            from tools.web_fetcher import web_fetch
            self.register("web_fetch", web_fetch)
            logger.info("Registered tool: web_fetch")
        except ImportError as e:
            logger.debug(f"web_fetch not available: {e}")
        
        try:
            from tools.browser.controller import BrowserController
            browser = BrowserController()
            self.register("browser_navigate", browser.navigate)
            self.register("browser_click", browser.click)
            self.register("browser_screenshot", browser.screenshot)
            self.register("browser_fill", browser.fill_form)
            logger.info("Registered tools: browser_*")
        except ImportError as e:
            logger.debug(f"browser tools not available: {e}")
        
        try:
            import requests
            def http_request(method: str, url: str, headers: Dict = None,
                           json: Dict = None, data: Any = None) -> Dict:
                resp = requests.request(method, url, headers=headers,
                                       json=json, data=data, timeout=30)
                result = {"status": resp.status_code, "body": resp.text[:50000]}
                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        result["json"] = resp.json()
                    except Exception:
                        result["json"] = None
                return result
            self.register("http_request", http_request)
            logger.info("Registered tool: http_request")
        except ImportError:
            logger.debug("requests not available for http_request")

        try:
            from tools.code_executor import execute_code
            self.register("execute_code", execute_code)
            logger.info("Registered tool: execute_code")
        except ImportError as e:
            logger.debug(f"execute_code not available: {e}")

    def register(self, name: str, fn: Callable) -> None:
        self._tools[name] = fn

    def has(self, name: str) -> bool:
        return name in self._tools

    def call(self, name: str, **kwargs) -> Any:
        if not self.has(name):
            raise ValueError(f"Tool '{name}' not registered")
        return self._tools[name](**kwargs)
    
    def list_tools(self) -> Dict[str, str]:
        """List all available tools and their function names."""
        return {name: fn.__name__ for name, fn in self._tools.items()}

    def get_tool(self, name: str) -> Dict[str, Any]:
        """Get tool spec by name."""
        if name not in self._tools:
            return None
        fn = self._tools[name]
        import inspect
        sig = inspect.signature(fn)
        return {"name": name, "schema": {k: str(v) for k, v in sig.parameters.items()}, "fn": fn}

    def __iter__(self):
        """Iterate over tool specs."""
        for name, fn in self._tools.items():
            import inspect
            sig = inspect.signature(fn)
            yield {"name": name, "description": f"Tool: {fn.__name__}", "schema": {k: str(v) for k, v in sig.parameters.items()}}


def get_tool(name: str) -> Dict[str, Any]:
    """Get tool spec by name from global registry."""
    return tool_registry.get_tool(name)


tool_registry = ToolRegistry()
