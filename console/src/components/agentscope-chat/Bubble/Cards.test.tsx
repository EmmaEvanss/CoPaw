import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Cards from "./Cards";

const cardConfigState = vi.hoisted(() => ({
  current: {} as Record<string, () => JSX.Element>,
}));

vi.mock("@/components/agentscope-chat", () => ({
  useChatAnywhere: () => ({}),
  useCustomCardsContext: () => cardConfigState.current,
}));

describe("Bubble Cards", () => {
  it("uses the latest custom card renderer after provider updates", () => {
    const cards = [{ code: "StatusCard", data: { version: 1 } }];
    cardConfigState.current = {
      StatusCard: () => <div>待反馈</div>,
    };

    const { rerender } = render(<Cards cards={cards} id="message-1" />);

    expect(screen.getByText("待反馈")).toBeInTheDocument();

    cardConfigState.current = {
      StatusCard: () => <div>反馈已提交</div>,
    };
    rerender(
      <Cards
        cards={[{ code: "StatusCard", data: { version: 2 } }]}
        id="message-1"
      />,
    );

    expect(screen.getByText("反馈已提交")).toBeInTheDocument();
  });
});
