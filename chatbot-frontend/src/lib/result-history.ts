const HISTORY_KEY = "jenkins-analysis-history-v1";
const MAX_HISTORY = 3;

type HistoryItem = {
	response: string;
	jobName?: string;
	buildNumber?: number | string;
	createdAt: number;
};

export type BacktrackSimilarity = {
	score: number;
	comparedCount: number;
	comparedWith: string[];
	overview: string;
	exactMatches: string[];
	topSharedTerms: string[];
	synonymousMatches: string[];
	comparisonDetails: Array<{
		label: string;
		score: number;
		sharedTerms: string[];
		synonymous: string[];
	}>;
};

const SYNONYM_GROUPS: Array<{ label: string; terms: string[] }> = [
	{ label: "Failure semantics", terms: ["failed", "failure", "error", "exception"] },
	{ label: "Timeout semantics", terms: ["timeout", "timed", "wait", "retry"] },
	{ label: "Selector semantics", terms: ["selector", "locator", "xpath", "css"] },
	{ label: "Assertion semantics", terms: ["assert", "assertion", "expected", "actual"] },
	{ label: "Auth semantics", terms: ["login", "signin", "authentication", "auth"] },
];

function safeJsonParse<T>(value: string | null, fallback: T): T {
	if (!value) return fallback;
	try {
		return JSON.parse(value) as T;
	} catch {
		return fallback;
	}
}

function normalize(text: string): string {
	return text
		.toLowerCase()
		.replace(/\s+/g, " ")
		.replace(/[^a-z0-9\s]/g, " ")
		.replace(/\s+/g, " ")
		.trim();
}

function toTokenSet(text: string): Set<string> {
	const tokens = normalize(text)
		.split(" ")
		.filter((t) => t.length > 2);
	return new Set(tokens);
}

function tokenJaccard(a: string, b: string): number {
	const aSet = toTokenSet(a);
	const bSet = toTokenSet(b);
	if (!aSet.size || !bSet.size) return 0;

	let intersection = 0;
	for (const token of aSet) {
		if (bSet.has(token)) intersection += 1;
	}
	const union = aSet.size + bSet.size - intersection;
	return union ? intersection / union : 0;
}

function toTrigrams(text: string): Set<string> {
	const clean = normalize(text).replace(/\s/g, "");
	const set = new Set<string>();
	for (let i = 0; i < clean.length - 2; i += 1) {
		set.add(clean.slice(i, i + 3));
	}
	return set;
}

function trigramJaccard(a: string, b: string): number {
	const aSet = toTrigrams(a);
	const bSet = toTrigrams(b);
	if (!aSet.size || !bSet.size) return 0;

	let intersection = 0;
	for (const tri of aSet) {
		if (bSet.has(tri)) intersection += 1;
	}
	const union = aSet.size + bSet.size - intersection;
	return union ? intersection / union : 0;
}

function combinedSimilarityPercent(current: string, previous: string): number {
	const tokenScore = tokenJaccard(current, previous);
	const trigramScore = trigramJaccard(current, previous);
	const combined = tokenScore * 0.7 + trigramScore * 0.3;
	return Math.round(combined * 100);
}

function formatHistoryLabel(item: HistoryItem): string {
	const name = item.jobName || "previous result";
	const build = item.buildNumber !== undefined ? `#${String(item.buildNumber)}` : "";
	return `${name}${build ? ` ${build}` : ""}`;
}

function topSharedTerms(current: string, previous: string, limit = 5): string[] {
	const currentTokens = toTokenSet(current);
	const previousTokens = toTokenSet(previous);
	const shared: string[] = [];

	for (const token of currentTokens) {
		if (previousTokens.has(token)) {
			shared.push(token);
		}
	}

	return shared.sort((a, b) => b.length - a.length).slice(0, limit);
}

function synonymMatches(current: string, previous: string): string[] {
	const currentTokens = toTokenSet(current);
	const previousTokens = toTokenSet(previous);
	const matches: string[] = [];

	for (const group of SYNONYM_GROUPS) {
		const currTerms = group.terms.filter((t) => currentTokens.has(t));
		const prevTerms = group.terms.filter((t) => previousTokens.has(t));
		if (!currTerms.length || !prevTerms.length) continue;

		const currentTerm = currTerms[0];
		const previousTerm = prevTerms[0];
		matches.push(`${group.label}: ${currentTerm} ↔ ${previousTerm}`);
	}

	return matches;
}

export function computeAndStoreBacktrackSimilarity(current: {
	response: string;
	jobName?: string;
	buildNumber?: number | string;
}): BacktrackSimilarity {
	if (typeof window === "undefined") {
		return {
			score: 0,
			comparedCount: 0,
			comparedWith: [],
			overview: "Session history is only available in the browser.",
			exactMatches: [],
			topSharedTerms: [],
			synonymousMatches: [],
			comparisonDetails: [],
		};
	}

	const history = safeJsonParse<HistoryItem[]>(sessionStorage.getItem(HISTORY_KEY), []).slice(0, MAX_HISTORY);
	const similarities = history.map((item) => ({
		label: formatHistoryLabel(item),
		score: combinedSimilarityPercent(current.response, item.response),
		sharedTerms: topSharedTerms(current.response, item.response),
		synonymous: synonymMatches(current.response, item.response),
	}));

	const best = similarities.reduce((max, item) => (item.score > max ? item.score : max), 0);

	const updated: HistoryItem[] = [
		{
			response: current.response,
			jobName: current.jobName,
			buildNumber: current.buildNumber,
			createdAt: Date.now(),
		},
		...history,
	].slice(0, MAX_HISTORY);

	sessionStorage.setItem(HISTORY_KEY, JSON.stringify(updated));

	if (!similarities.length) {
		return {
			score: 0,
			comparedCount: 0,
			comparedWith: [],
			overview: "No previous result in this browser session yet.",
			exactMatches: [],
			topSharedTerms: [],
			synonymousMatches: [],
			comparisonDetails: [],
		};
	}

	const comparisonDetails = similarities
		.slice()
		.sort((a, b) => b.score - a.score)
		.map((s) => ({
			label: s.label,
			score: s.score,
			sharedTerms: s.sharedTerms,
			synonymous: s.synonymous,
		}));

	const exactMatches = comparisonDetails.filter((d) => d.score === 100).map((d) => d.label);
	const aggregateSharedTerms = Array.from(
		new Set(comparisonDetails.flatMap((d) => d.sharedTerms))
	).slice(0, 8);
	const aggregateSynonymous = Array.from(
		new Set(comparisonDetails.flatMap((d) => d.synonymous))
	).slice(0, 8);

	return {
		score: best,
		comparedCount: similarities.length,
		comparedWith: similarities.map((s) => s.label),
		overview: `Compared with the last ${similarities.length} result(s) stored in this browser session.`,
		exactMatches,
		topSharedTerms: aggregateSharedTerms,
		synonymousMatches: aggregateSynonymous,
		comparisonDetails,
	};
}

