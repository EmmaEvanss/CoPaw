import { describe, expect, it } from "vitest";
import { buildClientKey } from "./clientKey";

describe("buildClientKey", () => {
  it("为英文名称生成稳定的可读 key", () => {
    const first = buildClientKey("Context7 MCP");
    const second = buildClientKey("Context7 MCP");

    expect(first).toBe(second);
    expect(first).toMatch(/^context7-mcp-[0-9a-f]{4}$/);
  });

  it("为中文名称生成稳定的 key，而不是时间戳", () => {
    const first = buildClientKey("天气查询");
    const second = buildClientKey("天气查询");

    expect(first).toBe(second);
    expect(first).not.toMatch(/^mcp-\d+$/);
    expect(first).toMatch(/^tian-qi-cha-xun-[0-9a-f]{4}$/);
  });

  it("同音不同字的名称生成不同 key", () => {
    const first = buildClientKey("天气查询");
    const second = buildClientKey("天气查寻");

    expect(first).not.toBe(second);
    expect(first).toMatch(/^tian-qi-cha-xun-[0-9a-f]{4}$/);
    expect(second).toMatch(/^tian-qi-cha-xun-[0-9a-f]{4}$/);
  });
});
