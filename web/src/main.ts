import "./styles.css";

type ObjectLabel = {
  object_id: string;
  canonical_label: string;
  aliases: string[];
};

type DailyPuzzle = {
  date: string;
  season_id: string;
  season_label: string;
  pair_id: string;
  ref_version: string;
  base: ObjectLabel;
  target: ObjectLabel;
  hard_negatives: ObjectLabel[];
};

type DailyPuzzleSummary = {
  date: string;
  pair_id: string;
  base: ObjectLabel;
  target: ObjectLabel;
  current: boolean;
};

type DailyPuzzlesResponse = {
  season_id: string;
  season_label: string;
  current_date: string;
  entries: DailyPuzzleSummary[];
};

type ScoreBucket = "fooled" | "failed" | "confused";
type LeaderboardKind = "score" | "efficiency" | "friend" | "funny";

type VerdictResponse = {
  score: number;
  percentile: number;
  raw: number;
  confidences: { Cy: number; Cx: number; negs: number[] };
  bucket: ScoreBucket;
  flags: { ocr_cheat: boolean; moderation: "pass" | "flag" };
  model_version: string;
  template_set_id: string;
  tau: number;
  computed_at: string;
  comment: AppraisalComment;
};

type AppraisalComment = {
  line: string;
  mood: "smug" | "delighted" | "suspicious" | "exasperated";
  source: string;
  template_id: string;
};

type Cosmetic = {
  cosmetic_id: string;
  kind: "palette";
  label: string;
  colors: string[];
  newly_unlocked: boolean;
};

type SubmissionResponse = VerdictResponse & {
  submission_id: string;
  season_id: string;
  rank: number | null;
  rewards: Cosmetic[];
};

type LeaderboardEntry = {
  rank: number;
  submission_id: string;
  season_id: string;
  user_id: string;
  display_name: string;
  score: number;
  percentile: number;
  raw: number;
  bucket: ScoreBucket;
  stroke_count: number;
  created_at: string;
  friend_code: string;
  funny_votes: number;
};

type LeaderboardResponse = {
  date: string;
  season_id: string;
  season_label: string;
  kind: LeaderboardKind;
  entries: LeaderboardEntry[];
};

type GhostResponse = {
  date: string;
  season_id: string;
  season_label: string;
  kind: LeaderboardKind;
  rank: number;
  submission_id: string;
  display_name: string;
  score: number;
  funny_votes: number;
  bucket: ScoreBucket;
  image_b64: string;
  stroke_log: { strokes: Stroke[] } | null;
};

type FunnyVoteResponse = {
  submission_id: string;
  funny_votes: number;
  accepted: boolean;
};

type ContentReportResponse = {
  report_id: string;
  submission_id: string;
  report_count: number;
  status: "recorded" | "duplicate";
};

type PlaytestFeedbackResponse = {
  feedback_id: string;
  submission_id: string;
  sentiment: "fun" | "hard" | "bug";
  status: "recorded" | "duplicate";
};

type AppraisalCommentResponse = {
  submission_id: string;
  comment: AppraisalComment;
  status:
    | "minted"
    | "cached"
    | "fallback_safety"
    | "fallback_user_quota"
    | "fallback_budget"
    | "fallback_unavailable"
    | "fallback_output_filter"
    | "fallback_hero_gate";
  daily_spend: number;
  daily_cap: number;
  user_remaining: number;
};

type CosmeticsResponse = {
  user_id: string;
  season_id: string;
  cosmetics: Cosmetic[];
};

type PremiumResponse = {
  user_id: string;
  premium: boolean;
  source: string;
};

type PremiumRedeemResponse = PremiumResponse & {
  code: string;
  status: "redeemed" | "already_redeemed" | "invalid" | "expired" | "exhausted";
};

type PairProposalResponse = {
  proposal_id: string;
  pair_key: string;
  user_id: string;
  base_label: string;
  target_label: string;
  base: (ObjectLabel & { category: string }) | null;
  target: (ObjectLabel & { category: string }) | null;
  status: "candidate" | "needs_catalog_review" | "approved" | "rejected";
  rejection_reasons: string[];
  difficulty_prior: number | null;
  hard_negatives: Array<ObjectLabel & { category: string }>;
  support_count: number;
  created_at: string;
  last_supported_at: string;
  reviewer_id: string;
  review_note: string;
  reviewed_at: string | null;
};

type StrokePoint = {
  x: number;
  y: number;
  t: number;
  pressure: number;
};

type Stroke = {
  color: string;
  size: number;
  mode: "draw" | "erase";
  points: StrokePoint[];
};

const API_BASE = resolveApiBase();
const HERO_APPRAISAL_PERCENTILE = 0.95;
const defaultPalette: Cosmetic = {
  cosmetic_id: "palette-classic",
  kind: "palette",
  label: "Classic",
  colors: ["#1f1d1a", "#e9e5d8", "#d6453d", "#2f875a", "#e7c24e", "#315f9d"],
  newly_unlocked: false,
};
const paletteOrder = ["palette-classic", "palette-verdict", "palette-masterpiece"];
const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Missing app root.");
}

app.innerHTML = `
  <main class="app">
    <header class="topbar">
      <div class="brand">
        <div class="brand-title">gitai</div>
        <div class="brand-subtitle">鑑定士</div>
      </div>
      <div class="top-actions">
        <label class="player">
          <span class="label">Player</span>
          <input class="player-input" id="display-name" type="text" maxlength="24" value="guest" />
        </label>
        <label class="friend">
          <span class="label">Circle</span>
          <span class="friend-control">
            <input class="friend-input" id="friend-code" type="text" maxlength="16" />
            <button class="friend-code-button" id="new-friend-code" type="button" title="新しい合言葉">↻</button>
            <button class="friend-code-button" id="share-friend-code" type="button" title="合言葉を共有">↗</button>
          </span>
        </label>
        <label class="pass">
          <span class="label">Pass</span>
          <span class="pass-control">
            <span class="pass-badge" id="premium-badge">Free</span>
            <input class="pass-input" id="premium-code" type="text" maxlength="32" placeholder="CODE" />
            <button class="pass-button" id="redeem-premium" type="button" title="コードを使う">✓</button>
          </span>
        </label>
        <div class="status"><span class="status-dot" id="status-dot"></span><span id="status-text">接続中</span></div>
        <nav class="policy-links" aria-label="公開情報">
          <a id="privacy-link" href="/privacy.html">Privacy</a>
          <a id="terms-link" href="/terms.html">Terms</a>
          <a id="safety-link" href="/safety.html">Safety</a>
          <a id="support-link" href="/support.html">Support</a>
        </nav>
      </div>
    </header>
    <section class="workspace">
      <aside class="panel briefing">
        <div class="briefing-header">
          <div class="label">Daily</div>
          <div class="challenge">
            <div class="challenge-row">
              <div class="object-name" id="base-name">...</div>
              <div class="arrow">→</div>
              <div class="object-name" id="target-name">...</div>
            </div>
            <label class="daily-picker">
              <span class="label">Day</span>
              <select class="daily-select" id="daily-select"></select>
            </label>
          </div>
        </div>
        <div class="reference">
          <canvas class="reference-canvas" id="reference-canvas" width="512" height="512"></canvas>
            <div class="stats">
              <div class="stat"><div class="label">Date</div><div class="stat-value" id="puzzle-date">...</div></div>
              <div class="stat"><div class="label">Season</div><div class="stat-value" id="season-label">...</div></div>
              <div class="stat"><div class="label">Try</div><div class="stat-value" id="stroke-count">0</div></div>
            </div>
          <div class="ghost-card">
            <div class="ghost-header">
              <span class="label">Top Ghost</span>
              <strong id="ghost-score">---</strong>
            </div>
            <div class="ghost-preview" id="ghost-preview">
              <canvas class="ghost-replay-canvas" id="ghost-replay-canvas" width="768" height="768"></canvas>
            </div>
            <div class="ghost-name" id="ghost-name">まだ相手がいません。</div>
            <div class="ghost-actions">
              <button class="ghost-replay" id="ghost-replay-button" type="button" disabled>Replay</button>
              <button class="ghost-vote" id="ghost-vote-button" type="button" disabled>Funny</button>
              <button class="ghost-report" id="ghost-report-button" type="button" disabled>Report</button>
            </div>
          </div>
        </div>
        <div class="tools">
          <div class="tool-row">
            <button class="tool-button active" id="draw-tool" title="筆">✎</button>
            <button class="tool-button" id="erase-tool" title="消し">⌫</button>
            <button class="tool-button" id="undo-tool" title="戻す">↶</button>
            <button class="tool-button" id="clear-tool" title="消去">×</button>
          </div>
          <div class="swatches" id="swatches"></div>
          <div class="tool-row">
            <span class="label">Palette</span>
            <select class="palette-select" id="palette-select"></select>
          </div>
          <div class="tool-row">
            <span class="label">Size</span>
            <input class="slider" id="size-slider" type="range" min="4" max="54" value="18" />
          </div>
        </div>
      </aside>
      <section class="panel stage">
        <div class="stage-header">
          <div>
            <div class="label">Canvas</div>
            <strong id="stage-title">素体を化けさせる</strong>
          </div>
          <div class="attempt" id="save-state">未提出</div>
        </div>
        <div class="canvas-wrap">
          <canvas class="draw-canvas" id="draw-canvas" width="768" height="768"></canvas>
          <div class="scan" id="scan"><div class="scan-line"></div></div>
        </div>
        <div class="stage-actions">
          <button class="secondary-button" id="reset-base">素体に戻す</button>
          <button class="secondary-button" id="replay-button" disabled>Replay</button>
          <button class="primary-button" id="submit-button">鑑定</button>
        </div>
      </section>
      <aside class="panel reveal">
        <div class="reveal-header">
          <div class="label">Verdict</div>
          <div class="score" id="score">---</div>
        </div>
        <div class="verdict">
          <div class="judge">
            <div class="judge-face" id="judge-face">◇</div>
            <div class="line" id="judge-line">まだ鑑定前です。</div>
          </div>
          <div class="result-grid">
            <div class="result-item"><span class="label">Target</span><strong id="cy">--</strong></div>
            <div class="result-item"><span class="label">Base</span><strong id="cx">--</strong></div>
            <div class="result-item"><span class="label">Top</span><strong id="percentile">--</strong></div>
            <div class="result-item"><span class="label">Raw</span><strong id="raw">--</strong></div>
            <div class="result-item"><span class="label">Bucket</span><strong id="bucket">--</strong></div>
          </div>
          <div class="rankline" id="rank-line">Rank --</div>
          <div class="playtest-feedback" aria-label="Playtest feedback">
            <button class="feedback-button" id="feedback-fun" type="button" disabled>楽しい</button>
            <button class="feedback-button" id="feedback-hard" type="button" disabled>難しい</button>
            <button class="feedback-button" id="feedback-bug" type="button" disabled>バグっぽい</button>
          </div>
          <div class="leaderboard">
            <div class="leaderboard-title">
              <span class="label">Ranking</span>
              <span id="leaderboard-date">--</span>
            </div>
            <div class="segmented" id="leaderboard-tabs">
              <button class="segment active" id="score-tab">Score</button>
              <button class="segment" id="efficiency-tab">Efficiency</button>
              <button class="segment" id="friend-tab">Friends</button>
              <button class="segment" id="funny-tab">Funny</button>
            </div>
            <ol class="leaderboard-list" id="leaderboard-list">
              <li class="leaderboard-empty">まだ記録がありません。</li>
            </ol>
          </div>
          <div class="pair-proposal">
            <div class="leaderboard-title">
              <span class="label">Next Pair</span>
              <span id="proposal-state">未提案</span>
            </div>
            <div class="proposal-row">
              <input class="proposal-input" id="proposal-base" type="text" maxlength="48" placeholder="base" />
              <span class="proposal-arrow">→</span>
              <input class="proposal-input" id="proposal-target" type="text" maxlength="48" placeholder="target" />
              <button class="proposal-button" id="proposal-button" type="button">提案</button>
            </div>
          </div>
          <div class="share-card">
            <div class="share-title" id="share-title">gitai</div>
            <div class="share-preview" id="share-preview"></div>
            <div>
              <div class="label">Score</div>
              <div class="share-score" id="share-score">---</div>
              <div class="share-percentile" id="share-percentile">Top --</div>
              <button class="share-action" id="appraiser-button" disabled>Appraiser</button>
              <button class="share-action" id="share-card-button" disabled>Share Card</button>
            </div>
          </div>
        </div>
      </aside>
    </section>
  </main>
`;

const statusDot = byId<HTMLSpanElement>("status-dot");
const statusText = byId<HTMLSpanElement>("status-text");
const drawCanvas = byId<HTMLCanvasElement>("draw-canvas");
const referenceCanvas = byId<HTMLCanvasElement>("reference-canvas");
const ghostReplayCanvas = byId<HTMLCanvasElement>("ghost-replay-canvas");
const drawContext = context2d(drawCanvas);
const referenceContext = context2d(referenceCanvas);
const ghostReplayContext = context2d(ghostReplayCanvas);
const scan = byId<HTMLDivElement>("scan");
const submitButton = byId<HTMLButtonElement>("submit-button");
const drawTool = byId<HTMLButtonElement>("draw-tool");
const eraseTool = byId<HTMLButtonElement>("erase-tool");
const undoTool = byId<HTMLButtonElement>("undo-tool");
const clearTool = byId<HTMLButtonElement>("clear-tool");
const resetBase = byId<HTMLButtonElement>("reset-base");
const replayButton = byId<HTMLButtonElement>("replay-button");
const sizeSlider = byId<HTMLInputElement>("size-slider");
const swatches = byId<HTMLDivElement>("swatches");
const paletteSelect = byId<HTMLSelectElement>("palette-select");
const displayNameInput = byId<HTMLInputElement>("display-name");
const friendCodeInput = byId<HTMLInputElement>("friend-code");
const newFriendCodeButton = byId<HTMLButtonElement>("new-friend-code");
const shareFriendCodeButton = byId<HTMLButtonElement>("share-friend-code");
const premiumBadge = byId<HTMLSpanElement>("premium-badge");
const premiumCodeInput = byId<HTMLInputElement>("premium-code");
const redeemPremiumButton = byId<HTMLButtonElement>("redeem-premium");
const scoreTab = byId<HTMLButtonElement>("score-tab");
const efficiencyTab = byId<HTMLButtonElement>("efficiency-tab");
const friendTab = byId<HTMLButtonElement>("friend-tab");
const funnyTab = byId<HTMLButtonElement>("funny-tab");
const shareCardButton = byId<HTMLButtonElement>("share-card-button");
const appraiserButton = byId<HTMLButtonElement>("appraiser-button");
const feedbackButtons = {
  fun: byId<HTMLButtonElement>("feedback-fun"),
  hard: byId<HTMLButtonElement>("feedback-hard"),
  bug: byId<HTMLButtonElement>("feedback-bug"),
};
const ghostVoteButton = byId<HTMLButtonElement>("ghost-vote-button");
const ghostReplayButton = byId<HTMLButtonElement>("ghost-replay-button");
const ghostReportButton = byId<HTMLButtonElement>("ghost-report-button");
const dailySelect = byId<HTMLSelectElement>("daily-select");
const proposalBaseInput = byId<HTMLInputElement>("proposal-base");
const proposalTargetInput = byId<HTMLInputElement>("proposal-target");
const proposalButton = byId<HTMLButtonElement>("proposal-button");
const proposalState = byId<HTMLSpanElement>("proposal-state");
const playerId = getOrCreatePlayerId();

let puzzle: DailyPuzzle | null = null;
let dailyPuzzles: DailyPuzzleSummary[] = [];
let palettes: Cosmetic[] = [defaultPalette];
let selectedPaletteId = localStorage.getItem("gitai.palette") ?? defaultPalette.cosmetic_id;
let activeColors = defaultPalette.colors;
let selectedColor = activeColors[0];
let brushSize = Number(sizeSlider.value);
let mode: "draw" | "erase" = "draw";
let strokes: Stroke[] = [];
let activeStroke: Stroke | null = null;
let drawingLocked = false;
let isReplaying = false;
let replayToken = 0;
let lastSubmissionId: string | null = null;
let visibleGhostSubmissionId: string | null = null;
let visibleGhostStrokeLog: Stroke[] | null = null;
let isGhostReplaying = false;
let ghostReplayToken = 0;
let leaderboardKind: LeaderboardKind = initialLeaderboardKind();
let hasPremium = false;

void boot();

async function boot(): Promise<void> {
  setupTools();
  setupCanvas();
  paintBlank();
  try {
    const archive = await fetchJson<DailyPuzzlesResponse>("/v1/daily-puzzles");
    dailyPuzzles = archive.entries;
    renderDailyPicker(archive.current_date);
    await loadPuzzle(selectedDailyDate(archive.current_date));
    setReady(true, "接続済み");
  } catch (error) {
    setReady(false, "オフライン");
    drawFallbackReference();
    resetToBase();
    console.error(error);
  }
}

function setupTools(): void {
  displayNameInput.value = localStorage.getItem("gitai.displayName") ?? "guest";
  displayNameInput.addEventListener("input", () => {
    localStorage.setItem("gitai.displayName", displayNameInput.value.trim() || "guest");
  });
  friendCodeInput.value = getOrCreateFriendCode();
  updateLeaderboardTabs();
  friendCodeInput.addEventListener("input", () => {
    friendCodeInput.value = normalizeFriendCode(friendCodeInput.value);
    localStorage.setItem("gitai.friendCode", friendCodeInput.value);
    if (leaderboardKind === "friend" && puzzle) {
      void refreshLeaderboard(puzzle.date);
      void refreshGhost(puzzle.date);
    }
  });
  newFriendCodeButton.addEventListener("click", () => {
    friendCodeInput.value = generateFriendCode();
    localStorage.setItem("gitai.friendCode", friendCodeInput.value);
    void setLeaderboardKind("friend");
  });
  shareFriendCodeButton.addEventListener("click", () => {
    void shareCircleInvite();
  });
  dailySelect.addEventListener("change", () => {
    if (!dailySelect.value) return;
    localStorage.setItem("gitai.dailyDate", dailySelect.value);
    void loadPuzzle(dailySelect.value);
  });
  premiumCodeInput.addEventListener("input", () => {
    premiumCodeInput.value = normalizeRedeemCode(premiumCodeInput.value);
  });
  premiumCodeInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void redeemPremiumCode();
    }
  });
  redeemPremiumButton.addEventListener("click", () => {
    void redeemPremiumCode();
  });
  proposalButton.addEventListener("click", () => {
    void submitPairProposal();
  });
  proposalBaseInput.addEventListener("keydown", submitPairProposalOnEnter);
  proposalTargetInput.addEventListener("keydown", submitPairProposalOnEnter);

  renderPaletteControls();
  paletteSelect.addEventListener("change", () => {
    selectedPaletteId = paletteSelect.value;
    localStorage.setItem("gitai.palette", selectedPaletteId);
    renderPaletteControls();
  });

  drawTool.addEventListener("click", () => {
    mode = "draw";
    updateToolState();
  });
  eraseTool.addEventListener("click", () => {
    mode = "erase";
    updateToolState();
  });
  undoTool.addEventListener("click", () => {
    if (isReplaying) return;
    strokes.pop();
    redrawAll();
  });
  clearTool.addEventListener("click", () => {
    if (isReplaying) return;
    resetToBase();
  });
  resetBase.addEventListener("click", () => {
    if (isReplaying) return;
    resetToBase();
  });
  sizeSlider.addEventListener("input", () => {
    brushSize = Number(sizeSlider.value);
  });
  submitButton.addEventListener("click", () => {
    void submitDrawing();
  });
  replayButton.addEventListener("click", () => {
    void replayDrawing();
  });
  shareCardButton.addEventListener("click", () => {
    void shareLastCard();
  });
  appraiserButton.addEventListener("click", () => {
    void requestAppraiserComment();
  });
  feedbackButtons.fun.addEventListener("click", () => {
    void submitPlaytestFeedback("fun");
  });
  feedbackButtons.hard.addEventListener("click", () => {
    void submitPlaytestFeedback("hard");
  });
  feedbackButtons.bug.addEventListener("click", () => {
    void submitPlaytestFeedback("bug");
  });
  scoreTab.addEventListener("click", () => {
    void setLeaderboardKind("score");
  });
  efficiencyTab.addEventListener("click", () => {
    void setLeaderboardKind("efficiency");
  });
  friendTab.addEventListener("click", () => {
    void setLeaderboardKind("friend");
  });
  funnyTab.addEventListener("click", () => {
    void setLeaderboardKind("funny");
  });
  ghostVoteButton.addEventListener("click", () => {
    void voteForVisibleGhost();
  });
  ghostReportButton.addEventListener("click", () => {
    void reportVisibleGhost();
  });
  ghostReplayButton.addEventListener("click", () => {
    void replayVisibleGhost();
  });
}

function setupCanvas(): void {
  drawCanvas.addEventListener("pointerdown", (event) => {
    if (drawingLocked) return;
    drawCanvas.setPointerCapture(event.pointerId);
    activeStroke = {
      color: selectedColor,
      size: brushSize,
      mode,
      points: [pointFromEvent(event)],
    };
    drawPoint(activeStroke);
  });
  drawCanvas.addEventListener("pointermove", (event) => {
    if (!activeStroke) return;
    activeStroke.points.push(pointFromEvent(event));
    drawStroke(activeStroke);
  });
  drawCanvas.addEventListener("pointerup", finishStroke);
  drawCanvas.addEventListener("pointercancel", finishStroke);
}

function finishStroke(): void {
  if (!activeStroke) return;
  if (activeStroke.points.length > 0) {
    strokes.push(activeStroke);
  }
  activeStroke = null;
  updateStrokeCount();
}

function pointFromEvent(event: PointerEvent): StrokePoint {
  const rect = drawCanvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * drawCanvas.width,
    y: ((event.clientY - rect.top) / rect.height) * drawCanvas.height,
    t: performance.now(),
    pressure: event.pressure || 0.5,
  };
}

function drawPoint(stroke: Stroke): void {
  drawPointOn(drawContext, stroke);
}

function drawPointOn(ctx: CanvasRenderingContext2D, stroke: Stroke): void {
  const point = stroke.points[0];
  if (!point) return;
  ctx.save();
  ctx.globalCompositeOperation = stroke.mode === "erase" ? "destination-out" : "source-over";
  ctx.fillStyle = stroke.color;
  ctx.beginPath();
  ctx.arc(point.x, point.y, stroke.size / 2, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawStroke(stroke: Stroke): void {
  const points = stroke.points;
  if (points.length < 2) {
    drawPoint(stroke);
    return;
  }
  const previous = points[points.length - 2];
  const current = points[points.length - 1];
  drawSegment(stroke, previous, current);
}

function drawSegment(stroke: Stroke, previous: StrokePoint, current: StrokePoint): void {
  drawSegmentOn(drawContext, stroke, previous, current);
}

function drawSegmentOn(
  ctx: CanvasRenderingContext2D,
  stroke: Stroke,
  previous: StrokePoint,
  current: StrokePoint,
): void {
  ctx.save();
  ctx.globalCompositeOperation = stroke.mode === "erase" ? "destination-out" : "source-over";
  ctx.strokeStyle = stroke.color;
  ctx.lineWidth = stroke.size;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(previous.x, previous.y);
  ctx.lineTo(current.x, current.y);
  ctx.stroke();
  ctx.restore();
}

function redrawAll(): void {
  paintBaseLayer();
  for (const stroke of strokes) {
    if (stroke.points.length === 1) {
      drawPoint(stroke);
      continue;
    }
    for (let index = 1; index < stroke.points.length; index += 1) {
      drawSegment(stroke, stroke.points[index - 1], stroke.points[index]);
    }
  }
  updateStrokeCount();
  updateReplayButton();
}

function paintBlank(): void {
  drawContext.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
  drawContext.fillStyle = "#ffffff";
  drawContext.fillRect(0, 0, drawCanvas.width, drawCanvas.height);
}

function paintBaseLayer(): void {
  paintBlank();
  if (!puzzle) return;
  drawBase(drawContext, drawCanvas, puzzle.base.object_id);
}

function resetToBase(): void {
  strokes = [];
  drawBase(drawContext, drawCanvas, puzzle?.base.object_id ?? "apple");
  updateStrokeCount();
  updateReplayButton();
}

async function replayDrawing(): Promise<void> {
  if (isReplaying || strokes.length === 0) return;
  const token = replayToken + 1;
  replayToken = token;
  const replayStrokes = cloneStrokes(strokes);
  isReplaying = true;
  setDrawingControlsDisabled(true);
  byId<HTMLSpanElement>("save-state").textContent = "再生中";
  try {
    paintBaseLayer();
    await wait(120);

    for (const stroke of replayStrokes) {
      if (token !== replayToken) return;
      if (stroke.points.length === 1) {
        drawPoint(stroke);
        await wait(24);
        continue;
      }
      for (let index = 1; index < stroke.points.length; index += 1) {
        drawSegment(stroke, stroke.points[index - 1], stroke.points[index]);
        await wait(replayDelay(stroke.points[index - 1], stroke.points[index]));
      }
    }

    if (token === replayToken) {
      strokes = replayStrokes;
      redrawAll();
    }
  } finally {
    if (token === replayToken) {
      isReplaying = false;
      setDrawingControlsDisabled(false);
      byId<HTMLSpanElement>("save-state").textContent = lastSubmissionId ? "鑑定済み" : "未提出";
      updateReplayButton();
    }
  }
}

function cloneStrokes(source: Stroke[]): Stroke[] {
  return source.map((stroke) => ({
    color: stroke.color,
    size: stroke.size,
    mode: stroke.mode,
    points: stroke.points.map((point) => ({ ...point })),
  }));
}

function replayDelay(previous: StrokePoint, current: StrokePoint): number {
  const elapsed = Math.max(0, current.t - previous.t);
  return Math.max(10, Math.min(42, elapsed / 18));
}

function setDrawingControlsDisabled(disabled: boolean): void {
  drawingLocked = disabled;
  drawTool.disabled = disabled;
  eraseTool.disabled = disabled;
  undoTool.disabled = disabled;
  clearTool.disabled = disabled;
  resetBase.disabled = disabled;
  submitButton.disabled = disabled;
  replayButton.disabled = disabled || strokes.length === 0;
  drawCanvas.classList.toggle("locked", disabled);
}

function updateReplayButton(): void {
  replayButton.disabled = drawingLocked || isReplaying || strokes.length === 0;
}

function drawBase(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement, objectId: string): void {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (objectId === "apple") {
    drawApple(ctx, canvas.width, canvas.height);
    return;
  }
  if (objectId === "orange") {
    drawRoundFruit(ctx, canvas.width, canvas.height, "#e88b2f", false);
    return;
  }
  if (objectId === "tomato") {
    drawRoundFruit(ctx, canvas.width, canvas.height, "#d7472f", true);
    return;
  }
  if (objectId === "tennis_ball") {
    drawTennisBall(ctx, canvas.width, canvas.height);
    return;
  }
  if (objectId === "balloon") {
    drawBalloon(ctx, canvas.width, canvas.height);
    return;
  }
  if (objectId === "banana") {
    drawBanana(ctx, canvas.width, canvas.height);
    return;
  }
  if (objectId === "mug") {
    drawMug(ctx, canvas.width, canvas.height);
    return;
  }
  if (objectId === "book") {
    drawBook(ctx, canvas.width, canvas.height);
    return;
  }
  if (objectId === "car") {
    drawCar(ctx, canvas.width, canvas.height);
    return;
  }
  if (objectId === "chair") {
    drawChair(ctx, canvas.width, canvas.height);
    return;
  }
  ctx.fillStyle = "#e9e5d8";
  ctx.beginPath();
  ctx.arc(canvas.width / 2, canvas.height / 2, canvas.width * 0.28, 0, Math.PI * 2);
  ctx.fill();
}

function drawApple(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  const scale = width / 512;
  ctx.save();
  ctx.scale(scale, height / 512);
  ctx.fillStyle = "#6c3b22";
  roundRect(ctx, 238, 74, 38, 80, 16);
  ctx.fill();
  ctx.fillStyle = "#559246";
  ctx.beginPath();
  ctx.ellipse(302, 108, 38, 18, -0.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#d22f35";
  ctx.beginPath();
  ctx.ellipse(196, 256, 92, 132, -0.08, 0, Math.PI * 2);
  ctx.ellipse(316, 256, 92, 132, 0.08, 0, Math.PI * 2);
  ctx.rect(170, 258, 172, 142);
  ctx.fill();
  ctx.restore();
}

function drawRoundFruit(ctx: CanvasRenderingContext2D, width: number, height: number, color: string, leafy: boolean): void {
  ctx.save();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.ellipse(width / 2, height / 2 + height * 0.03, width * 0.26, height * 0.28, 0, 0, Math.PI * 2);
  ctx.fill();
  if (leafy) {
    ctx.fillStyle = "#2f875a";
    for (let index = 0; index < 5; index += 1) {
      ctx.beginPath();
      ctx.ellipse(width / 2, height * 0.28, width * 0.04, height * 0.10, (index * Math.PI) / 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.restore();
}

function drawTennisBall(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.save();
  ctx.fillStyle = "#d9df4a";
  ctx.beginPath();
  ctx.arc(width / 2, height / 2, width * 0.28, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#f7f5ee";
  ctx.lineWidth = width * 0.035;
  ctx.beginPath();
  ctx.arc(width * 0.35, height / 2, width * 0.25, -Math.PI / 2, Math.PI / 2);
  ctx.arc(width * 0.65, height / 2, width * 0.25, Math.PI / 2, (Math.PI * 3) / 2);
  ctx.stroke();
  ctx.restore();
}

function drawBalloon(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.save();
  ctx.fillStyle = "#d7472f";
  ctx.beginPath();
  ctx.ellipse(width / 2, height * 0.40, width * 0.24, height * 0.30, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#8b4538";
  ctx.beginPath();
  ctx.moveTo(width / 2, height * 0.70);
  ctx.lineTo(width * 0.47, height * 0.76);
  ctx.lineTo(width * 0.53, height * 0.76);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = "#5f574d";
  ctx.lineWidth = width * 0.012;
  ctx.beginPath();
  ctx.moveTo(width / 2, height * 0.76);
  ctx.bezierCurveTo(width * 0.45, height * 0.86, width * 0.55, height * 0.92, width * 0.50, height * 0.98);
  ctx.stroke();
  ctx.restore();
}

function drawBanana(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.save();
  ctx.strokeStyle = "#e3bd32";
  ctx.lineWidth = width * 0.12;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(width * 0.28, height * 0.58);
  ctx.quadraticCurveTo(width * 0.52, height * 0.76, width * 0.76, height * 0.42);
  ctx.stroke();
  ctx.strokeStyle = "#8b6a1f";
  ctx.lineWidth = width * 0.025;
  ctx.beginPath();
  ctx.moveTo(width * 0.25, height * 0.56);
  ctx.lineTo(width * 0.20, height * 0.54);
  ctx.moveTo(width * 0.78, height * 0.40);
  ctx.lineTo(width * 0.83, height * 0.36);
  ctx.stroke();
  ctx.restore();
}

function drawMug(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.save();
  ctx.fillStyle = "#fffdf7";
  ctx.strokeStyle = "#2b2722";
  ctx.lineWidth = width * 0.025;
  roundRect(ctx, width * 0.30, height * 0.32, width * 0.32, height * 0.34, width * 0.04);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(width * 0.65, height * 0.48, width * 0.11, -Math.PI / 2, Math.PI / 2);
  ctx.stroke();
  ctx.restore();
}

function drawBook(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.save();
  ctx.fillStyle = "#315f9d";
  roundRect(ctx, width * 0.27, height * 0.25, width * 0.46, height * 0.50, width * 0.025);
  ctx.fill();
  ctx.strokeStyle = "#fffdf7";
  ctx.lineWidth = width * 0.018;
  ctx.beginPath();
  ctx.moveTo(width * 0.38, height * 0.25);
  ctx.lineTo(width * 0.38, height * 0.75);
  ctx.stroke();
  ctx.restore();
}

function drawCar(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.save();
  ctx.fillStyle = "#d7472f";
  roundRect(ctx, width * 0.22, height * 0.45, width * 0.56, height * 0.16, width * 0.04);
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(width * 0.36, height * 0.45);
  ctx.lineTo(width * 0.45, height * 0.34);
  ctx.lineTo(width * 0.60, height * 0.34);
  ctx.lineTo(width * 0.68, height * 0.45);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#2b2722";
  ctx.beginPath();
  ctx.arc(width * 0.34, height * 0.62, width * 0.055, 0, Math.PI * 2);
  ctx.arc(width * 0.66, height * 0.62, width * 0.055, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawChair(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.save();
  ctx.strokeStyle = "#6c3b22";
  ctx.fillStyle = "#8b5a32";
  ctx.lineWidth = width * 0.035;
  roundRect(ctx, width * 0.34, height * 0.30, width * 0.32, height * 0.22, width * 0.02);
  ctx.fill();
  ctx.stroke();
  roundRect(ctx, width * 0.31, height * 0.52, width * 0.38, height * 0.12, width * 0.02);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(width * 0.36, height * 0.64);
  ctx.lineTo(width * 0.30, height * 0.82);
  ctx.moveTo(width * 0.64, height * 0.64);
  ctx.lineTo(width * 0.70, height * 0.82);
  ctx.stroke();
  ctx.restore();
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number): void {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + width, y, x + width, y + height, radius);
  ctx.arcTo(x + width, y + height, x, y + height, radius);
  ctx.arcTo(x, y + height, x, y, radius);
  ctx.arcTo(x, y, x + width, y, radius);
  ctx.closePath();
}

function drawFallbackReference(): void {
  drawBase(referenceContext, referenceCanvas, "apple");
}

function renderDailyPicker(currentDate: string): void {
  dailySelect.replaceChildren(
    ...dailyPuzzles.map((entry) => {
      const option = document.createElement("option");
      option.value = entry.date;
      option.textContent = `${entry.date.slice(5)} ${entry.base.canonical_label} → ${entry.target.canonical_label}${
        entry.current ? " / Today" : ""
      }`;
      return option;
    })
  );
  dailySelect.value = selectedDailyDate(currentDate);
}

function selectedDailyDate(currentDate: string): string {
  const saved = localStorage.getItem("gitai.dailyDate") ?? "";
  if (dailyPuzzles.some((entry) => entry.date === saved)) {
    return saved;
  }
  return currentDate;
}

async function loadPuzzle(date: string): Promise<void> {
  const loaded = await fetchJson<DailyPuzzle>(`/v1/daily-puzzle?date=${encodeURIComponent(date)}`);
  puzzle = loaded;
  dailySelect.value = loaded.date;
  bindPuzzle(loaded);
  drawBase(referenceContext, referenceCanvas, loaded.base.object_id);
  resetToBase();
  resetVerdict();
  await refreshPremium();
  await refreshCosmetics();
  await refreshLeaderboard(loaded.date);
  await refreshGhost(loaded.date);
}

function resetVerdict(): void {
  lastSubmissionId = null;
  byId<HTMLDivElement>("score").textContent = "---";
  byId<HTMLDivElement>("share-score").textContent = "---";
  byId<HTMLDivElement>("share-percentile").textContent = "Top --";
  byId<HTMLDivElement>("rank-line").textContent = "Rank --";
  byId<HTMLDivElement>("cy").textContent = "--";
  byId<HTMLDivElement>("cx").textContent = "--";
  byId<HTMLDivElement>("percentile").textContent = "--";
  byId<HTMLDivElement>("raw").textContent = "--";
  byId<HTMLDivElement>("bucket").textContent = "--";
  byId<HTMLDivElement>("judge-face").textContent = "◇";
  byId<HTMLDivElement>("judge-line").textContent = "まだ鑑定前です。";
  byId<HTMLDivElement>("share-title").textContent = "gitai";
  byId<HTMLDivElement>("share-preview").style.backgroundImage = "";
  byId<HTMLSpanElement>("save-state").textContent = "未提出";
  shareCardButton.disabled = true;
  appraiserButton.disabled = true;
  setFeedbackButtonsDisabled(true);
}

async function submitDrawing(): Promise<void> {
  if (!puzzle || drawingLocked) return;
  setDrawingControlsDisabled(true);
  scan.classList.add("active");
  byId<HTMLSpanElement>("save-state").textContent = "鑑定中";
  await wait(900);
  try {
    const image_b64 = drawCanvas.toDataURL("image/png").split(",")[1] ?? "";
    const result = await postJson<SubmissionResponse>("/v1/submissions", {
      image_b64,
      pair_id: puzzle.pair_id,
      ref_version: puzzle.ref_version,
      puzzle_date: puzzle.date,
      user_id: playerId,
      display_name: displayNameInput.value.trim() || "guest",
      friend_code: friendCodeInput.value,
      stroke_log: { strokes },
    });
    renderResult(result);
    await refreshLeaderboard(puzzle.date);
    await refreshGhost(puzzle.date);
    byId<HTMLSpanElement>("save-state").textContent = "鑑定済み";
  } catch (error) {
    console.error(error);
    byId<HTMLDivElement>("judge-line").textContent = submissionErrorLine(error);
    byId<HTMLSpanElement>("save-state").textContent = "失敗";
  } finally {
    scan.classList.remove("active");
    setDrawingControlsDisabled(false);
  }
}

function renderResult(result: SubmissionResponse): void {
  lastSubmissionId = result.submission_id;
  mergeCosmetics(result.rewards);
  const scoreText = String(result.score).padStart(3, "0");
  const percentileText = formatTopPercentile(result.percentile);
  const rankText = result.rank ? `Rank #${result.rank} / ${percentileText}` : percentileText;
  byId<HTMLDivElement>("score").textContent = scoreText;
  byId<HTMLDivElement>("share-score").textContent = scoreText;
  byId<HTMLDivElement>("share-percentile").textContent = percentileText;
  byId<HTMLDivElement>("rank-line").textContent = rankText;
  byId<HTMLDivElement>("cy").textContent = `${Math.round(result.confidences.Cy * 100)}%`;
  byId<HTMLDivElement>("cx").textContent = `${Math.round(result.confidences.Cx * 100)}%`;
  byId<HTMLDivElement>("percentile").textContent = percentileText;
  byId<HTMLDivElement>("raw").textContent = result.raw.toFixed(3);
  byId<HTMLDivElement>("bucket").textContent = result.bucket;
  byId<HTMLDivElement>("judge-face").textContent = faceForMood(result.comment.mood);
  byId<HTMLDivElement>("judge-line").textContent = result.comment.line || judgeLine(result);
  byId<HTMLDivElement>("share-title").textContent =
    `${puzzle?.base.canonical_label} → ${puzzle?.target.canonical_label}`;
  byId<HTMLDivElement>("share-preview").style.backgroundImage = `url(${shareCardUrl(result.submission_id)})`;
  shareCardButton.disabled = false;
  appraiserButton.disabled = false;
  setFeedbackButtonsDisabled(false);
  if (result.rewards.length > 0) {
    flashStatus(`${result.rewards[0].label} unlocked`);
  }
  void maybeRequestHeroAppraisal(result);
}

function judgeLine(result: VerdictResponse): string {
  if (result.flags.ocr_cheat) {
    return "文字の気配が強すぎますね。これは鑑定対象ではなく看板です。";
  }
  const target = puzzle?.target.canonical_label ?? "target";
  const base = puzzle?.base.canonical_label ?? "base";
  if (result.bucket === "fooled") {
    return `これは見事な${target}です。疑う余地は、私の辞書にはありません。`;
  }
  if (result.bucket === "confused") {
    return `${base}と${target}の境界で、鑑定士としての威厳が揺れています。`;
  }
  return `${base}が${target}の装いをしています。努力の筆跡は、確かにあります。`;
}

function faceForMood(mood: AppraisalComment["mood"]): string {
  if (mood === "delighted") return "◆";
  if (mood === "suspicious") return "◇";
  if (mood === "exasperated") return "◈";
  return "◆";
}

async function refreshLeaderboard(date: string): Promise<void> {
  try {
    const board = await fetchJson<LeaderboardResponse>(leaderboardUrl(date));
    renderLeaderboard(board);
  } catch (error) {
    console.error(error);
    byId<HTMLOListElement>("leaderboard-list").replaceChildren(rowText("ランキングを取得できません。"));
  }
}

function renderLeaderboard(board: LeaderboardResponse): void {
  byId<HTMLSpanElement>("leaderboard-date").textContent = `${board.season_label} / ${board.date.slice(5)}`;
  const list = byId<HTMLOListElement>("leaderboard-list");
  if (board.entries.length === 0) {
    list.replaceChildren(rowText("まだ記録がありません。"));
    return;
  }
  list.replaceChildren(...board.entries.map((entry) => leaderboardRow(entry)));
}

async function refreshGhost(date: string): Promise<void> {
  try {
    const ghost = await fetchJson<GhostResponse>(ghostUrl(date));
    renderGhost(ghost);
  } catch (error) {
    console.error(error);
    visibleGhostSubmissionId = null;
    visibleGhostStrokeLog = null;
    clearGhostReplayCanvas();
    byId<HTMLDivElement>("ghost-preview").style.backgroundImage = "";
    byId<HTMLDivElement>("ghost-score").textContent = "---";
    byId<HTMLDivElement>("ghost-name").textContent = "まだ相手がいません。";
    ghostVoteButton.disabled = true;
    ghostReplayButton.disabled = true;
    ghostReportButton.disabled = true;
  }
}

function renderGhost(ghost: GhostResponse): void {
  ghostReplayToken += 1;
  isGhostReplaying = false;
  visibleGhostSubmissionId = ghost.submission_id;
  visibleGhostStrokeLog = strokesFromLog(ghost.stroke_log);
  clearGhostReplayCanvas();
  byId<HTMLDivElement>("ghost-preview").style.backgroundImage = `url(data:image/png;base64,${ghost.image_b64})`;
  byId<HTMLDivElement>("ghost-score").textContent = String(ghost.score).padStart(3, "0");
  byId<HTMLDivElement>("ghost-name").textContent =
    ghost.funny_votes > 0 ? `#${ghost.rank} ${ghost.display_name} / ${ghost.funny_votes}票` : `#${ghost.rank} ${ghost.display_name}`;
  ghostVoteButton.disabled = ghost.submission_id === lastSubmissionId;
  ghostReplayButton.disabled = !visibleGhostStrokeLog;
  ghostReportButton.disabled = false;
}

async function replayVisibleGhost(): Promise<void> {
  if (!puzzle || !visibleGhostStrokeLog || isGhostReplaying) return;
  const token = ghostReplayToken + 1;
  ghostReplayToken = token;
  const replayStrokes = cloneStrokes(visibleGhostStrokeLog);
  isGhostReplaying = true;
  ghostReplayButton.disabled = true;
  clearGhostReplayCanvas();
  drawBase(ghostReplayContext, ghostReplayCanvas, puzzle.base.object_id);
  await wait(120);

  try {
    for (const stroke of replayStrokes) {
      if (token !== ghostReplayToken) return;
      if (stroke.points.length === 1) {
        drawPointOn(ghostReplayContext, stroke);
        await wait(24);
        continue;
      }
      for (let index = 1; index < stroke.points.length; index += 1) {
        drawSegmentOn(ghostReplayContext, stroke, stroke.points[index - 1], stroke.points[index]);
        await wait(replayDelay(stroke.points[index - 1], stroke.points[index]));
      }
    }
  } finally {
    if (token === ghostReplayToken) {
      isGhostReplaying = false;
      ghostReplayButton.disabled = !visibleGhostStrokeLog;
    }
  }
}

function clearGhostReplayCanvas(): void {
  ghostReplayContext.clearRect(0, 0, ghostReplayCanvas.width, ghostReplayCanvas.height);
}

function strokesFromLog(strokeLog: { strokes: Stroke[] } | null): Stroke[] | null {
  if (!strokeLog || !Array.isArray(strokeLog.strokes) || strokeLog.strokes.length === 0) return null;
  const parsed: Stroke[] = [];
  for (const stroke of strokeLog.strokes) {
    if (!stroke || (stroke.mode !== "draw" && stroke.mode !== "erase")) return null;
    if (typeof stroke.color !== "string" || !/^#[0-9a-fA-F]{6}$/.test(stroke.color)) return null;
    if (!Number.isFinite(stroke.size) || stroke.size <= 0 || stroke.size > 128) return null;
    if (!Array.isArray(stroke.points) || stroke.points.length === 0) return null;
    const points: StrokePoint[] = [];
    for (const point of stroke.points) {
      if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return null;
      points.push({
        x: point.x,
        y: point.y,
        t: Number.isFinite(point.t) ? point.t : 0,
        pressure: Number.isFinite(point.pressure) ? point.pressure : 0.5,
      });
    }
    parsed.push({ color: stroke.color, size: stroke.size, mode: stroke.mode, points });
  }
  return parsed;
}

async function setLeaderboardKind(kind: LeaderboardKind): Promise<void> {
  leaderboardKind = kind;
  updateLeaderboardTabs();
  if (!puzzle) return;
  await refreshLeaderboard(puzzle.date);
  await refreshGhost(puzzle.date);
}

function updateLeaderboardTabs(): void {
  scoreTab.classList.toggle("active", leaderboardKind === "score");
  efficiencyTab.classList.toggle("active", leaderboardKind === "efficiency");
  friendTab.classList.toggle("active", leaderboardKind === "friend");
  funnyTab.classList.toggle("active", leaderboardKind === "funny");
}

function leaderboardRow(entry: LeaderboardEntry): HTMLLIElement {
  const row = document.createElement("li");
  row.className = `leaderboard-row${entry.submission_id === lastSubmissionId ? " mine" : ""}`;

  const rank = document.createElement("span");
  rank.className = "leaderboard-rank";
  rank.textContent = `#${entry.rank}`;

  const name = document.createElement("span");
  name.className = "leaderboard-name";
  name.textContent = entry.display_name;

  const meta = document.createElement("span");
  meta.className = "leaderboard-meta";
  const top = formatTopPercentile(entry.percentile);
  if (leaderboardKind === "efficiency") {
    meta.textContent = `${entry.stroke_count}筆 / ${entry.score} / ${top}`;
  } else if (leaderboardKind === "funny") {
    meta.textContent = `${entry.funny_votes}票 / ${entry.score} / ${top}`;
  } else {
    meta.textContent = `${entry.score} / ${top}`;
  }

  row.append(rank, name, meta);
  return row;
}

function rowText(text: string): HTMLLIElement {
  const row = document.createElement("li");
  row.className = "leaderboard-empty";
  row.textContent = text;
  return row;
}

function formatTopPercentile(percentile: number): string {
  const clamped = Math.max(0, Math.min(1, percentile));
  const top = Math.max(0, Math.min(100, (1 - clamped) * 100));
  if (top === 0 && clamped > 0) return "Top 1%";
  if (top < 1 && clamped > 0) return "Top 1%";
  if (top < 10) return `Top ${top.toFixed(1)}%`;
  return `Top ${Math.round(top)}%`;
}

function bindPuzzle(value: DailyPuzzle): void {
  byId<HTMLDivElement>("base-name").textContent = value.base.canonical_label;
  byId<HTMLDivElement>("target-name").textContent = value.target.canonical_label;
  byId<HTMLDivElement>("puzzle-date").textContent = value.date.slice(5);
  byId<HTMLDivElement>("season-label").textContent = value.season_label;
  byId<HTMLDivElement>("stage-title").textContent = `${value.base.canonical_label} を ${value.target.canonical_label} へ`;
  proposalBaseInput.placeholder = value.base.canonical_label;
  proposalTargetInput.placeholder = value.target.canonical_label;
}

function updateToolState(): void {
  drawTool.classList.toggle("active", mode === "draw");
  eraseTool.classList.toggle("active", mode === "erase");
  document.querySelectorAll<HTMLButtonElement>(".swatch").forEach((button) => {
    button.classList.toggle("active", button.style.backgroundColor === hexToRgb(selectedColor));
  });
}

async function refreshCosmetics(): Promise<void> {
  if (!puzzle) return;
  try {
    const params = new URLSearchParams({
      user_id: playerId,
      season_id: puzzle.season_id,
    });
    const response = await fetchJson<CosmeticsResponse>(`/v1/cosmetics?${params.toString()}`);
    mergeCosmetics(response.cosmetics);
  } catch (error) {
    console.error(error);
  }
}

async function refreshPremium(): Promise<void> {
  try {
    const params = new URLSearchParams({ user_id: playerId });
    const response = await fetchJson<PremiumResponse>(`/v1/premium?${params.toString()}`);
    renderPremium(response);
  } catch (error) {
    console.error(error);
    renderPremium({ user_id: playerId, premium: false, source: "none" });
  }
}

function renderPremium(response: PremiumResponse): void {
  hasPremium = response.premium;
  premiumBadge.textContent = hasPremium ? "Pass" : "Free";
  premiumBadge.classList.toggle("active", hasPremium);
  premiumCodeInput.disabled = hasPremium;
  redeemPremiumButton.disabled = hasPremium;
}

async function redeemPremiumCode(): Promise<void> {
  const code = normalizeRedeemCode(premiumCodeInput.value);
  if (!code) {
    flashStatus("Codeなし");
    return;
  }
  redeemPremiumButton.disabled = true;
  try {
    const response = await postJson<PremiumRedeemResponse>("/v1/premium/redeem", {
      user_id: playerId,
      code,
    });
    renderPremium(response);
    if (response.premium) {
      premiumCodeInput.value = "";
    }
    flashStatus(premiumStatusText(response));
  } catch (error) {
    console.error(error);
    flashStatus("Pass失敗");
  } finally {
    redeemPremiumButton.disabled = hasPremium;
  }
}

function premiumStatusText(response: PremiumRedeemResponse): string {
  if (response.status === "redeemed") return "Pass active";
  if (response.status === "already_redeemed") return "Pass active";
  if (response.status === "exhausted") return "Code満席";
  if (response.status === "expired") return "Code期限切れ";
  return "Code無効";
}

function submitPairProposalOnEnter(event: KeyboardEvent): void {
  if (event.key !== "Enter") return;
  event.preventDefault();
  void submitPairProposal();
}

async function submitPairProposal(): Promise<void> {
  const baseLabel = proposalBaseInput.value.trim();
  const targetLabel = proposalTargetInput.value.trim();
  if (!baseLabel || !targetLabel) {
    proposalState.textContent = "空欄あり";
    return;
  }
  proposalButton.disabled = true;
  proposalState.textContent = "送信中";
  try {
    const response = await postJson<PairProposalResponse>("/v1/pair-proposals", {
      user_id: playerId,
      base_label: baseLabel,
      target_label: targetLabel,
    });
    proposalState.textContent = pairProposalStatusText(response);
    if (response.status !== "rejected") {
      proposalBaseInput.value = "";
      proposalTargetInput.value = "";
    }
    flashStatus(pairProposalFlashText(response));
  } catch (error) {
    console.error(error);
    proposalState.textContent = "失敗";
  } finally {
    proposalButton.disabled = false;
  }
}

function pairProposalStatusText(response: PairProposalResponse): string {
  const support = pairProposalSupportText(response);
  if (response.status === "approved") return `採用候補${support}`;
  if (response.status === "candidate") return `候補入り${support}`;
  if (response.status === "needs_catalog_review") return `レビュー待ち${support}`;
  return `見送り${support}`;
}

function pairProposalFlashText(response: PairProposalResponse): string {
  if (response.status === "approved") return `採用候補${pairProposalSupportText(response)}`;
  if (response.status === "candidate") {
    const difficulty = response.difficulty_prior === null ? "--" : response.difficulty_prior.toFixed(2);
    return `候補入り${pairProposalSupportText(response)} ${difficulty}`;
  }
  if (response.status === "needs_catalog_review") {
    return `レビュー待ち${pairProposalSupportText(response)}`;
  }
  return `今回は見送り${pairProposalSupportText(response)}`;
}

function pairProposalSupportText(response: PairProposalResponse): string {
  return response.support_count > 1 ? ` x${response.support_count}` : "";
}

function mergeCosmetics(items: Cosmetic[]): void {
  if (items.length === 0) return;
  const byId = new Map(palettes.map((item) => [item.cosmetic_id, item]));
  for (const item of items) {
    if (item.kind === "palette") {
      byId.set(item.cosmetic_id, item);
    }
  }
  palettes = Array.from(byId.values()).sort(
    (a, b) => paletteSortIndex(a.cosmetic_id) - paletteSortIndex(b.cosmetic_id)
  );
  renderPaletteControls();
}

function paletteSortIndex(cosmeticId: string): number {
  const index = paletteOrder.indexOf(cosmeticId);
  return index === -1 ? paletteOrder.length : index;
}

function renderPaletteControls(): void {
  if (!palettes.some((item) => item.cosmetic_id === selectedPaletteId)) {
    selectedPaletteId = defaultPalette.cosmetic_id;
  }
  paletteSelect.replaceChildren(
    ...palettes.map((palette) => {
      const option = document.createElement("option");
      option.value = palette.cosmetic_id;
      option.textContent = palette.label;
      return option;
    })
  );
  paletteSelect.value = selectedPaletteId;
  const selected = palettes.find((item) => item.cosmetic_id === selectedPaletteId) ?? defaultPalette;
  activeColors = selected.colors.length > 0 ? selected.colors : defaultPalette.colors;
  if (!activeColors.includes(selectedColor)) {
    selectedColor = activeColors[0];
  }
  renderSwatches();
  updateToolState();
}

function renderSwatches(): void {
  swatches.replaceChildren(
    ...activeColors.map((color) => {
      const button = document.createElement("button");
      button.className = `swatch${color === selectedColor ? " active" : ""}`;
      button.style.background = color;
      button.title = color;
      button.addEventListener("click", () => {
        selectedColor = color;
        mode = "draw";
        updateToolState();
      });
      return button;
    })
  );
}

function updateStrokeCount(): void {
  byId<HTMLDivElement>("stroke-count").textContent = String(strokes.length);
}

function setReady(ready: boolean, text: string): void {
  statusDot.classList.toggle("ready", ready);
  statusText.textContent = text;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path));
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<T>;
}

async function responseErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    if (body.detail) {
      return body.detail;
    }
  } catch {
    return `${response.status} ${response.statusText}`;
  }
  return `${response.status} ${response.statusText}`;
}

function submissionErrorLine(error: unknown): string {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("stroke") || message.includes("replay")) {
    return "提出画像を再生できませんでした。キャンバスからもう一度送ってください。";
  }
  if (message.includes("daily submission limit")) {
    return "本日の挑戦回数に達しました。鑑定士は明日また席を空けます。";
  }
  return "鑑定台が少し騒がしいようです。";
}

async function requestAppraiserComment(): Promise<void> {
  if (!lastSubmissionId) return;
  appraiserButton.disabled = true;
  try {
    const result = await postJson<AppraisalCommentResponse>("/v1/appraisal-comments", {
      submission_id: lastSubmissionId,
      user_id: playerId,
      mode: "on_demand",
    });
    byId<HTMLDivElement>("judge-face").textContent = faceForMood(result.comment.mood);
    byId<HTMLDivElement>("judge-line").textContent = result.comment.line;
    flashStatus(appraiserStatusText(result));
  } catch (error) {
    console.error(error);
    flashStatus("鑑定士は不在です");
  } finally {
    appraiserButton.disabled = false;
  }
}

async function shareLastCard(): Promise<void> {
  if (!lastSubmissionId) return;
  const url = shareCardUrl(lastSubmissionId);
  const title = "gitai";
  const text = puzzle
    ? `${puzzle.base.canonical_label} → ${puzzle.target.canonical_label}`
    : "gitai";

  shareCardButton.disabled = true;
  try {
    if (navigator.share) {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const blob = await response.blob();
      const file = new File([blob], "gitai-share-card.png", { type: blob.type || "image/png" });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title, text });
        flashStatus("共有しました");
        return;
      }
      await navigator.share({ title, text, url });
      flashStatus("共有しました");
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  } catch (error) {
    if (!(error instanceof DOMException && error.name === "AbortError")) {
      console.error(error);
    }
    window.open(url, "_blank", "noopener,noreferrer");
  } finally {
    shareCardButton.disabled = false;
  }
}

async function maybeRequestHeroAppraisal(result: SubmissionResponse): Promise<void> {
  if (!isHeroAppraisalEligible(result)) return;
  const submissionId = result.submission_id;
  appraiserButton.disabled = true;
  flashStatus("特別鑑定中");
  try {
    const minted = await postJson<AppraisalCommentResponse>("/v1/appraisal-comments", {
      submission_id: submissionId,
      user_id: playerId,
      mode: "hero",
    });
    if (lastSubmissionId !== submissionId) return;
    if (minted.comment.source === "layer2") {
      byId<HTMLDivElement>("judge-face").textContent = faceForMood(minted.comment.mood);
      byId<HTMLDivElement>("judge-line").textContent = minted.comment.line;
    }
    flashStatus(appraiserStatusText(minted));
  } catch (error) {
    console.error(error);
  } finally {
    if (lastSubmissionId === submissionId) {
      appraiserButton.disabled = false;
    }
  }
}

function isHeroAppraisalEligible(result: SubmissionResponse): boolean {
  return (
    result.percentile >= HERO_APPRAISAL_PERCENTILE &&
    !result.flags.ocr_cheat &&
    result.flags.moderation === "pass"
  );
}

function appraiserStatusText(result: AppraisalCommentResponse): string {
  if (result.status === "minted") return "鑑定士コメント更新";
  if (result.status === "cached") return "鑑定済み";
  if (result.status === "fallback_budget") return `本日は満席 ${result.daily_spend}/${result.daily_cap}`;
  if (result.status === "fallback_user_quota") return "本日分は終了";
  if (result.status === "fallback_hero_gate") return "通常鑑定";
  return "通常鑑定";
}

async function voteForVisibleGhost(): Promise<void> {
  if (!visibleGhostSubmissionId || !puzzle) return;
  ghostVoteButton.disabled = true;
  try {
    const result = await postJson<FunnyVoteResponse>("/v1/funny-votes", {
      submission_id: visibleGhostSubmissionId,
      user_id: playerId,
    });
    flashStatus(result.accepted ? "Funny +1" : "投票済み");
    await refreshLeaderboard(puzzle.date);
    await refreshGhost(puzzle.date);
  } catch (error) {
    console.error(error);
    flashStatus(error instanceof Error && error.message.includes("own") ? "自分には投票不可" : "投票できません");
  } finally {
    ghostVoteButton.disabled = visibleGhostSubmissionId === lastSubmissionId || !visibleGhostSubmissionId;
  }
}

async function reportVisibleGhost(): Promise<void> {
  if (!visibleGhostSubmissionId) return;
  ghostReportButton.disabled = true;
  try {
    const result = await postJson<ContentReportResponse>("/v1/content-reports", {
      submission_id: visibleGhostSubmissionId,
      user_id: playerId,
      reason: "unsafe",
      note: "reported from ghost card",
    });
    flashStatus(result.status === "recorded" ? "通報を記録" : "通報済み");
  } catch (error) {
    console.error(error);
    flashStatus("通報できません");
  } finally {
    ghostReportButton.disabled = !visibleGhostSubmissionId;
  }
}

async function submitPlaytestFeedback(sentiment: PlaytestFeedbackResponse["sentiment"]): Promise<void> {
  if (!lastSubmissionId) return;
  setFeedbackButtonsDisabled(true);
  try {
    const result = await postJson<PlaytestFeedbackResponse>("/v1/playtest-feedback", {
      submission_id: lastSubmissionId,
      user_id: playerId,
      sentiment,
    });
    flashStatus(result.status === "recorded" ? feedbackStatusText(result.sentiment) : "記録済み");
  } catch (error) {
    console.error(error);
    flashStatus("記録できません");
  } finally {
    setFeedbackButtonsDisabled(!lastSubmissionId);
  }
}

function setFeedbackButtonsDisabled(disabled: boolean): void {
  for (const button of Object.values(feedbackButtons)) {
    button.disabled = disabled;
  }
}

function feedbackStatusText(sentiment: PlaytestFeedbackResponse["sentiment"]): string {
  if (sentiment === "fun") return "楽しいを記録";
  if (sentiment === "hard") return "難しいを記録";
  return "バグっぽいを記録";
}

async function shareCircleInvite(): Promise<void> {
  const text = `gitai Circle ${friendCodeInput.value}\n${inviteUrl()}`;
  try {
    if (typeof navigator.share === "function") {
      await navigator.share({ title: "gitai", text, url: inviteUrl() });
    } else {
      await copyToClipboard(text);
      flashStatus("招待をコピー");
    }
  } catch (error) {
    console.error(error);
    try {
      await copyToClipboard(text);
      flashStatus("招待をコピー");
    } catch {
      flashStatus("共有できません");
    }
  }
}

async function copyToClipboard(text: string): Promise<void> {
  await window.navigator.clipboard.writeText(text);
}

function inviteUrl(): string {
  const url = new URL(window.location.href);
  url.searchParams.set("circle", friendCodeInput.value);
  return url.toString();
}

function flashStatus(text: string): void {
  const previous = statusText.textContent ?? "";
  statusText.textContent = text;
  window.setTimeout(() => {
    statusText.textContent = previous;
  }, 1400);
}

function shareCardUrl(submissionId: string): string {
  return apiUrl(`/v1/share-card?submission_id=${encodeURIComponent(submissionId)}`);
}

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function resolveApiBase(): string {
  const runtime = window.GITAI_API_BASE?.trim();
  if (runtime) return runtime.replace(/\/+$/, "");
  const configured = import.meta.env.VITE_GITAI_API_BASE?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  if (import.meta.env.DEV) return "http://127.0.0.1:8000";
  return "";
}

function leaderboardUrl(date: string): string {
  const params = new URLSearchParams({
    date,
    season_id: puzzle?.season_id ?? "",
    kind: leaderboardKind,
    limit: "10",
  });
  if (leaderboardKind === "friend") {
    params.set("friend_code", friendCodeInput.value);
  }
  return `/v1/leaderboard?${params.toString()}`;
}

function ghostUrl(date: string): string {
  const params = new URLSearchParams({
    date,
    season_id: puzzle?.season_id ?? "",
    kind: leaderboardKind,
  });
  if (leaderboardKind === "friend") {
    params.set("friend_code", friendCodeInput.value);
  }
  return `/v1/ghost?${params.toString()}`;
}

function byId<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element: ${id}`);
  }
  return element as T;
}

function context2d(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Canvas 2D is unavailable.");
  }
  return context;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function getOrCreatePlayerId(): string {
  const existing = localStorage.getItem("gitai.playerId");
  if (existing) return existing;
  const generated =
    "randomUUID" in crypto ? crypto.randomUUID() : `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  localStorage.setItem("gitai.playerId", generated);
  return generated;
}

function getOrCreateFriendCode(): string {
  const invited = normalizeFriendCode(new URLSearchParams(window.location.search).get("circle") ?? "");
  if (invited) {
    localStorage.setItem("gitai.friendCode", invited);
    return invited;
  }
  const existing = normalizeFriendCode(localStorage.getItem("gitai.friendCode") ?? "");
  if (existing) return existing;
  const generated = generateFriendCode();
  localStorage.setItem("gitai.friendCode", generated);
  return generated;
}

function generateFriendCode(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => alphabet[byte % alphabet.length]).join("");
}

function initialLeaderboardKind(): LeaderboardKind {
  const invited = normalizeFriendCode(new URLSearchParams(window.location.search).get("circle") ?? "");
  return invited ? "friend" : "score";
}

function normalizeFriendCode(value: string): string {
  return value
    .toUpperCase()
    .split("")
    .filter((char) => /[A-Z0-9-]/.test(char))
    .join("")
    .slice(0, 16);
}

function normalizeRedeemCode(value: string): string {
  return value
    .toUpperCase()
    .split("")
    .filter((char) => /[A-Z0-9-]/.test(char))
    .join("")
    .slice(0, 32);
}

function hexToRgb(hex: string): string {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgb(${r}, ${g}, ${b})`;
}
