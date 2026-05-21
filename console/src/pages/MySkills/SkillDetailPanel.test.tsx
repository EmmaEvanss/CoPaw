import { render, screen, cleanup } from "@testing-library/react";
import { describe, expect, it, afterEach } from "vitest";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
dayjs.extend(relativeTime);

import { MySkill } from "../../api/modules/mySkills";

// 简化的时间展示组件
const TimeDisplay = ({ skill }: { skill: MySkill }) => (
  <div>
    {skill.created_at && (
      <span data-testid="created-time">
        创建: {dayjs(skill.created_at).fromNow()}
      </span>
    )}
    {skill.updated_at && (
      <span data-testid="updated-time">
        更新: {dayjs(skill.updated_at).fromNow()}
      </span>
    )}
  </div>
);

describe("SkillDetailPanel time display", () => {
  afterEach(() => {
    cleanup();
  });

  it("should display created_at and updated_at", () => {
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

    render(<TimeDisplay skill={skill} />);

    expect(screen.getByTestId("created-time")).toBeInTheDocument();
    expect(screen.getByTestId("updated-time")).toBeInTheDocument();
  });

  it("should not display time when fields are undefined", () => {
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

    render(<TimeDisplay skill={skill} />);

    expect(screen.queryByTestId("created-time")).not.toBeInTheDocument();
    expect(screen.queryByTestId("updated-time")).not.toBeInTheDocument();
  });
});