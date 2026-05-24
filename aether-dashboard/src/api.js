const ENGINE_API = 'http://localhost:8100';
const BRAIN_API = 'http://localhost:8000';

async function fetchJSON(url, opts = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), 45000); // 45s timeout
  
  try {
    const res = await fetch(url, { 
      ...opts, 
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...opts.headers } 
    });
    clearTimeout(id);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    clearTimeout(id);
    console.error(`API Error [${url}]:`, err);
    return { _error: err.message || 'Timeout or Network Error' };
  }
}

// ─── Engine API ─────────────────────────────────────────────────
// NOTE: api/engine_api.py (port 8100) is optional — falls back gracefully
export const engineState = () => fetchJSON(`${ENGINE_API}/engine/state`)
  .catch(() => ({ _error: 'Engine API not available' }));
export const engineProcess = (query) => fetchJSON(`${ENGINE_API}/engine/process`, { method: 'POST', body: JSON.stringify({ query }) })
  .catch(() => ({ _error: 'Engine API not available' }));
export const engineResults = () => fetchJSON(`${ENGINE_API}/engine/results`)
  .catch(() => ({ results: [] }));

// ─── Betting ────────────────────────────────────────────────────
export const bettingSheet = (sport = 'basketball_nba', bankroll = 1000) =>
  fetchJSON(`${BRAIN_API}/betting/sheet?sport=${sport}&bankroll=${bankroll}`);
export const bettingOdds = (sport = 'basketball_nba') =>
  fetchJSON(`${BRAIN_API}/betting/odds?sport=${sport}`);
export const bettingEnhanced = (sport = 'basketball_nba', bankroll = 1000) =>
  fetchJSON(`${BRAIN_API}/betting/enhanced?sport=${sport}&bankroll=${bankroll}`);
export const bettingTrends = (player, market = 'points', line = 25) =>
  fetchJSON(`${BRAIN_API}/betting/trends?player=${encodeURIComponent(player)}&market=${market}&line=${line}`);
export const bettingPrizePicks = () =>
  fetchJSON(`${BRAIN_API}/betting/prizepicks`);
export const bettingPlace = (player, market, line) =>
  fetchJSON(`${BRAIN_API}/betting/place`, { method: 'POST', body: JSON.stringify({ player, market, line }) });

// ─── Trading / Finance ──────────────────────────────────────────
export const tradingPrice = (symbol = 'BTC-USD') =>
  fetchJSON(`${BRAIN_API}/trading/price?symbol=${symbol}`);
export const tradingBalance = () => fetchJSON(`${BRAIN_API}/trading/balance`);
export const tradingExecute = (symbol, side, amount) =>
  fetchJSON(`${BRAIN_API}/trading/execute`, { method: 'POST', body: JSON.stringify({ symbol, side, amount }) });

// ─── Social ─────────────────────────────────────────────────────
export const socialPosts = () => fetchJSON(`${BRAIN_API}/social/posts`);
export const socialSchedule = (platform, content, delay = 0) =>
  fetchJSON(`${BRAIN_API}/social/schedule?platform=${platform}&content=${encodeURIComponent(content)}&delay_minutes=${delay}`, { method: 'POST' });
export const socialPostDue = () =>
  fetchJSON(`${BRAIN_API}/social/post-due`, { method: 'POST' });

// ─── Planner ────────────────────────────────────────────────────
export const plannerTasks = () => fetchJSON(`${BRAIN_API}/planner/tasks`);
export const plannerAdd = (title, query, schedule = 'now') =>
  fetchJSON(`${BRAIN_API}/planner/tasks?title=${encodeURIComponent(title)}&query=${encodeURIComponent(query)}&schedule=${schedule}`, { method: 'POST' });
export const plannerRunDue = () => fetchJSON(`${BRAIN_API}/planner/run-due`, { method: 'POST' });

// ─── Soul / Settings ────────────────────────────────────────────
export const soulGet = () => fetchJSON(`${BRAIN_API}/soul`);
export const soulUpdate = (data) => fetchJSON(`${BRAIN_API}/soul`, { method: 'POST', body: JSON.stringify(data) });
export const settingsSaveKeys = (keys) => fetchJSON(`${BRAIN_API}/settings/keys`, { method: 'POST', body: JSON.stringify(keys) });
export const integrationsStatus = () => fetchJSON(`${BRAIN_API}/integrations`);

// ─── News ───────────────────────────────────────────────────────
export const newsFeed = () => fetchJSON(`${BRAIN_API}/news`);

// ─── Knowledge ──────────────────────────────────────────────────
export const knowledgeStats = () => fetchJSON(`${BRAIN_API}/knowledge/stats`);
export const knowledgeSearch = (query, top_k = 5) =>
  fetchJSON(`${BRAIN_API}/knowledge/search`, { method: 'POST', body: JSON.stringify({ query, top_k }) });

// ─── Chains ─────────────────────────────────────────────────────
export const chainsList = () => fetchJSON(`${BRAIN_API}/chains`);
export const chainsRun = (name, dryRun = false) =>
  fetchJSON(`${BRAIN_API}/chains/${name}/run`, { method: 'POST', body: JSON.stringify({ dry_run: dryRun }) });

// ─── SaaS Builder ───────────────────────────────────────────────
export const saasProjects = () => fetchJSON(`${BRAIN_API}/saas/projects`);
export const saasCreate = (name, idea) =>
  fetchJSON(`${BRAIN_API}/saas/create?name=${encodeURIComponent(name)}&idea=${encodeURIComponent(idea)}`, { method: 'POST' });

// ─── Health / LLM ───────────────────────────────────────────────
export const healthCheck = () => fetchJSON(`${BRAIN_API}/health`);
export const llmStatus = () => fetchJSON(`${BRAIN_API}/llm-status`);
export const autonomyStatus = () => fetchJSON(`${BRAIN_API}/autonomy/status`);
export const autonomyCEO = () => fetchJSON(`${BRAIN_API}/autonomy/ceo`);
export const systemsRegistry = () => fetchJSON(`${BRAIN_API}/systems/registry`);
export const systemsHealth = () => fetchJSON(`${BRAIN_API}/systems/health`);

// ─── Media ──────────────────────────────────────────────────────
export const mediaGenerate = (data) => fetchJSON(`${BRAIN_API}/media/generate`, { method: 'POST', body: JSON.stringify(data) });
export const mediaLibrary = () => fetchJSON(`${BRAIN_API}/media/library`);
export const skillsList = () => fetchJSON(`${BRAIN_API}/skills/list`);

// ─── Intelligence ──────────────────────────────────────────────
export const newsUnified = () => fetchJSON(`${BRAIN_API}/news/unified`);
export const newsSummarize = (title, url) => fetchJSON(`${BRAIN_API}/news/summarize`, { method: 'POST', body: JSON.stringify({ title, url }) });
export const newsAction = (action, title) => fetchJSON(`${BRAIN_API}/news/action`, { method: 'POST', body: JSON.stringify({ action, title }) });
export const opportunitiesList = () => fetchJSON(`${BRAIN_API}/opportunities`);

// ─── Uploads ────────────────────────────────────────────────────
export const uploadAgent = (name, content) => fetchJSON(`${BRAIN_API}/upload/agent`, { method: 'POST', body: JSON.stringify({ name, content }) });
export const uploadFolder = (name, desc = '') => fetchJSON(`${BRAIN_API}/upload/folder?name=${name}&description=${desc}`, { method: 'POST' });
export const knowledgeSynthesize = (tag) => fetchJSON(`${BRAIN_API}/knowledge/synthesize?tag=${tag}`, { method: 'POST' });

// ─── Brain Ops ───────────────────────────────────────────────────
export const brainReason = (query) => fetchJSON(`${BRAIN_API}/reason`, { method: 'POST', body: JSON.stringify({ query }) });
export const brainTask = (query) => fetchJSON(`${BRAIN_API}/task`, { method: 'POST', body: JSON.stringify({ query }) });
export const brainBundles = () => fetchJSON(`${BRAIN_API}/bundles`);

// ─── Cron & KAIROS ───────────────────────────────────────────────
export const kairosStatus = () => fetchJSON(`${BRAIN_API}/kairos/status`);
export const autodreamRun = () => fetchJSON(`${BRAIN_API}/autodream/run`, { method: 'POST' });
export const autonomyTick = () => fetchJSON(`${BRAIN_API}/autonomy/tick`, { method: 'POST' });
export const autonomyDream = () => fetchJSON(`${BRAIN_API}/autonomy/dream`, { method: 'POST' });
export const schedulerTasks = () => fetchJSON(`${BRAIN_API}/scheduler/tasks`);
export const dashboardFeed = () => fetchJSON(`${BRAIN_API}/dashboard/feed`);
export const knowledgeConsolidate = (dryRun = true) => fetchJSON(`${BRAIN_API}/knowledge/consolidate?dry_run=${dryRun}`, { method: 'POST' });

// ─── GitHub ──────────────────────────────────────────────────────
export const githubSearch = (q, perPage = 20) => fetchJSON(`${BRAIN_API}/github/search?q=${encodeURIComponent(q)}&per_page=${perPage}`);
export const githubClone = (owner, repo) => fetchJSON(`${BRAIN_API}/github/clone?owner=${owner}&repo=${repo}`, { method: 'POST' });
export const githubExpandSkills = (max = 5) => fetchJSON(`${BRAIN_API}/github/expand-skills?max_downloads=${max}`, { method: 'POST' });

// ─── Skill Expander ──────────────────────────────────────────────
export const skillsExpand = (max = 5) => fetchJSON(`${BRAIN_API}/skills/expand?max_downloads=${max}`, { method: 'POST' });
export const skillsRegistry = () => fetchJSON(`${BRAIN_API}/skills/list`);

// ─── Planner Tasks ───────────────────────────────────────────────
export const plannerTimeline = (hours = 24) => fetchJSON(`${BRAIN_API}/planner/timeline?hours=${hours}`);
export const plannerGenerateFromSoul = () => fetchJSON(`${BRAIN_API}/planner/generate-from-soul`, { method: 'POST' });

// ─── Cron / KAIROS (scheduler management) ─────────────────────────
export const cronScheduleRaw = () => fetchJSON(`${BRAIN_API}/scheduler/tasks`);
export const cronToggle = (name) => fetchJSON(`${BRAIN_API}/scheduler/tasks/${encodeURIComponent(name)}/toggle`, { method: 'PUT' });
export const cronDelete = (name) => fetchJSON(`${BRAIN_API}/scheduler/tasks/${encodeURIComponent(name)}`, { method: 'DELETE' });
export const cronAdd = (data) => fetchJSON(`${BRAIN_API}/scheduler/tasks`, { method: 'POST', body: JSON.stringify(data) });
export const cronRunDue = () => fetchJSON(`${BRAIN_API}/scheduler/run-due`, { method: 'POST' });

// ─── GitHub (used by GitHubManager page) ──────────────────────────
export const githubSearchRaw = (q, perPage = 20) => fetchJSON(`${BRAIN_API}/github/search?q=${encodeURIComponent(q)}&per_page=${perPage}`);
export const githubCloneRaw = (owner, repo) => fetchJSON(`${BRAIN_API}/github/clone?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}`, { method: 'POST' });
export const githubExpandSkillsRaw = (max = 5) => fetchJSON(`${BRAIN_API}/github/expand-skills?max_downloads=${max}`, { method: 'POST' });

// ─── Browser / Task dispatch ──────────────────────────────────────
export const taskDispatch = (query) => fetchJSON(`${BRAIN_API}/task`, { method: 'POST', body: JSON.stringify({ query }) });

// ─── Research Lab ─────────────────────────────────────────────────
export const labExperiment = (id, hypothesis, datasetId = 'default-biotech-v1') =>
  fetchJSON(`${BRAIN_API}/lab/experiment`, { method: 'POST', body: JSON.stringify({ id, hypothesis, dataset_id: datasetId }) });
export const labPaper = (experimentId) =>
  fetchJSON(`${BRAIN_API}/lab/paper`, { method: 'POST', body: JSON.stringify({ experiment_id: experimentId }) });

// ─── Content / Text generation ────────────────────────────────────
export const contentGenerateText = (topic, platform) =>
  fetchJSON(`${BRAIN_API}/task`, { method: 'POST', body: JSON.stringify({ query: `Generate a high-engagement ${platform} social media post about: ${topic}` }) });

// ─── Hermes ───────────────────────────────────────────────────────
export const hermesStatus = () => fetchJSON(`${BRAIN_API}/hermes/status`);
export const hermesChat = (text) =>
  fetchJSON(`${BRAIN_API}/hermes/chat`, { method: 'POST', body: JSON.stringify({ text }) });
export const hermesSkills = () => fetchJSON(`${BRAIN_API}/hermes/skills`);
export const hermesToggleSkill = (id) =>
  fetchJSON(`${BRAIN_API}/hermes/skills/${id}/toggle`, { method: 'POST' });
export const hermesCron = () => fetchJSON(`${BRAIN_API}/hermes/cron`);
export const hermesCreateCron = (data) =>
  fetchJSON(`${BRAIN_API}/hermes/cron`, { method: 'POST', body: JSON.stringify(data) });
export const hermesSessions = () => fetchJSON(`${BRAIN_API}/hermes/sessions`);
export const hermesSessionMessages = (id) =>
  fetchJSON(`${BRAIN_API}/hermes/sessions/${id}/messages`);
export const hermesModels = () => fetchJSON(`${BRAIN_API}/hermes/models`);
export const hermesAssignModel = (data) =>
  fetchJSON(`${BRAIN_API}/hermes/models/assign`, { method: 'POST', body: JSON.stringify(data) });

// ─── Local Model ──────────────────────────────────────────────────
export const localModelStatus = () => fetchJSON(`${BRAIN_API}/models/local/status`);
export const localModelChat = (text) =>
  fetchJSON(`${BRAIN_API}/models/local/chat`, { method: 'POST', body: JSON.stringify({ text }) });

// ─── Tools ────────────────────────────────────────────────────────
export const toolsRegister = (name, type, config) =>
  fetchJSON(`${BRAIN_API}/tools/register`, { method: 'POST', body: JSON.stringify({ name, type, config }) });
export const toolsList = () => fetchJSON(`${BRAIN_API}/tools`);
export const toolsExecute = (name, input) =>
  fetchJSON(`${BRAIN_API}/tools/${name}/execute`, { method: 'POST', body: JSON.stringify({ input }) });

// ─── Acquisition Tracker ─────────────────────────────────────
export const getAcquisitionStatus = () => fetchJSON(`${BRAIN_API}/api/acquisition/status`);
export const getAcquisitionLog = () => fetchJSON(`${BRAIN_API}/api/acquisition/daily-log`);
export const postAcquisitionLog = (data) => fetchJSON(`${BRAIN_API}/api/acquisition/daily-log`, { method: 'POST', body: JSON.stringify(data) });
export const getAcquisitionProgress = () => fetchJSON(`${BRAIN_API}/api/acquisition/progress`);
export const postAcquisitionProgress = (data) => fetchJSON(`${BRAIN_API}/api/acquisition/progress`, { method: 'POST', body: JSON.stringify(data) });
export const getAcquisitionInsights = () => fetchJSON(`${BRAIN_API}/api/acquisition/insights`);
export const postAcquisitionInsight = (data) => fetchJSON(`${BRAIN_API}/api/acquisition/insights`, { method: 'POST', body: JSON.stringify(data) });
export const getAcquisitionMetrics = () => fetchJSON(`${BRAIN_API}/api/acquisition/metrics`);
export const postAcquisitionMetrics = (data) => fetchJSON(`${BRAIN_API}/api/acquisition/metrics`, { method: 'POST', body: JSON.stringify(data) });
