import { describe, expect, it } from "vitest";
import { categoryFromScore, MATCH_CATEGORY_LABELS } from "@/lib/matching";
import { externalUrlLabel } from "@/lib/application-label";

describe("categoryFromScore", () => {
  it("classifies scores", () => {
    expect(categoryFromScore(95)).toBe("excellent");
    expect(categoryFromScore(85)).toBe("excellent");
    expect(categoryFromScore(84)).toBe("strong");
    expect(categoryFromScore(70)).toBe("strong");
    expect(categoryFromScore(60)).toBe("good");
    expect(categoryFromScore(50)).toBe("good");
    expect(categoryFromScore(20)).toBe("potential");
  });
});

describe("MATCH_CATEGORY_LABELS", () => {
  it("has labels for every category", () => {
    expect(MATCH_CATEGORY_LABELS.excellent).toBe("Excellent Match");
    expect(MATCH_CATEGORY_LABELS.potential).toBe("Potential Match");
  });
});

describe("externalUrlLabel", () => {
  it("extracts domain", () => {
    expect(externalUrlLabel("https://jobs.ashbyhq.com/acme")).toBe("jobs");
    expect(externalUrlLabel("https://www.google.com/jobs")).toBe("google");
  });

  it("falls back on invalid url", () => {
    expect(externalUrlLabel("not a url")).toBe("Open");
  });
});