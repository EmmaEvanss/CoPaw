import { describe, expect, it } from "vitest";
import { MySkill } from "./mySkills";

describe("MySkill type", () => {
  it("should accept created_at and updated_at fields", () => {
    const skill: MySkill = {
      skill_name: "test_skill",
      display_name: "Test Skill",
      source: "customized",
      description: "A test skill",
      version: "1.0.0",
      received_version: null,
      distributed_by: null,
      is_received: false,
      has_update: false,
      enabled: true,
      created_at: "2025-05-14T10:00:00Z",
      updated_at: "2025-05-14T12:00:00Z",
    };
    expect(skill.created_at).toBe("2025-05-14T10:00:00Z");
    expect(skill.updated_at).toBe("2025-05-14T12:00:00Z");
  });

  it("should allow optional time fields", () => {
    const skill: MySkill = {
      skill_name: "test_skill",
      display_name: "Test Skill",
      source: "customized",
      description: "A test skill",
      version: null,
      received_version: null,
      distributed_by: null,
      is_received: false,
      has_update: false,
      enabled: true,
    };
    expect(skill.created_at).toBeUndefined();
    expect(skill.updated_at).toBeUndefined();
  });
});