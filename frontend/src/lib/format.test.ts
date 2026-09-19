import { describe, expect, it } from "vitest";
import {
  employmentTypeLabel,
  experienceLevelLabel,
  formatPostedAt,
  formatSalaryMinMax,
  initials,
  locationLabel,
  workplaceTypeLabel,
} from "@/lib/format";

describe("formatSalaryMinMax", () => {
  it("returns text when present", () => {
    expect(formatSalaryMinMax(1, 2, "USD", "₹18-25 LPA")).toBe("₹18-25 LPA");
  });

  it("formats min only", () => {
    expect(formatSalaryMinMax(120000, null, "USD", null)).toBe("$120k+");
  });

  it("formats range", () => {
    expect(formatSalaryMinMax(80000, 120000, "USD", null)).toBe("$80k – $120k");
  });

  it("falls back when no data", () => {
    expect(formatSalaryMinMax(null, null, "USD", null)).toBe("Salary not disclosed");
    expect(formatSalaryMinMax(undefined, undefined, undefined, undefined)).toBe(
      "Salary not disclosed"
    );
  });
});

describe("locationLabel", () => {
  it("handles remote worldwide", () => {
    expect(
      locationLabel({ is_remote: true, remote_scope: "worldwide" })
    ).toBe("Remote (Worldwide)");
  });

  it("handles remote india", () => {
    expect(locationLabel({ is_remote: true, remote_scope: "india" })).toBe(
      "Remote (India)"
    );
  });

  it("handles ordinary remote", () => {
    expect(locationLabel({ is_remote: true, remote_scope: "none" })).toBe("Remote");
  });

  it("joins city, state, country", () => {
    expect(
      locationLabel({ city: "Bengaluru", state: "Karnataka", country: "India" })
    ).toBe("Bengaluru, Karnataka, India");
  });

  it("falls back to raw", () => {
    expect(locationLabel({ raw: "Pune, Maharashtra, India" })).toBe(
      "Pune, Maharashtra, India"
    );
    expect(locationLabel({})).toBe("Location not specified");
  });
});

describe("formatPostedAt", () => {
  it("handles null", () => {
    expect(formatPostedAt(null)).toBe("Posted date unknown");
  });

  it("handles today relative", () => {
    const now = new Date();
    expect(formatPostedAt(now.toISOString(), true)).toBe("Posted today");
  });

  it("handles invalid dates", () => {
    expect(formatPostedAt("not-a-date", false)).toBe("Posted date unknown");
  });
});

describe("labels", () => {
  it("maps employment types", () => {
    expect(employmentTypeLabel("internship")).toBe("Internship");
    expect(employmentTypeLabel("unknown-type")).toBe("unknown-type");
  });

  it("maps workplace types", () => {
    expect(workplaceTypeLabel("hybrid")).toBe("Hybrid");
  });

  it("maps experience levels with fallback", () => {
    expect(experienceLevelLabel("fresher")).toBe("Fresher");
    expect(experienceLevelLabel(undefined)).toBe("Any level");
    expect(experienceLevelLabel(null)).toBe("Any level");
  });
});

describe("initials", () => {
  it("extracts initials", () => {
    expect(initials("Priya Sharma")).toBe("PS");
    expect(initials(" one ")).toBe("O");
    expect(initials("")).toBe("");
  });
});