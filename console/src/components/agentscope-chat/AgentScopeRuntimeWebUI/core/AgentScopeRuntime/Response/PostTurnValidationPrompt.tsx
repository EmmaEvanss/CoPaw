import { Button } from "antd";
import { useProviderContext } from "@/components/agentscope-chat";
import { emit } from "../../Context/useChatAnywhereEventEmitter";
import Style from "./style";

interface PostTurnValidationPromptProps {
  data: {
    id: string;
    status: "needs_confirmation" | "dismissed" | "consumed";
    reason?: string;
    expires_at?: number;
  };
}

export default function PostTurnValidationPrompt(
  props: PostTurnValidationPromptProps,
) {
  const prefixCls = useProviderContext().getPrefixCls(
    "post-turn-validation",
  );
  const { data } = props;

  if (data.status !== "needs_confirmation") {
    return null;
  }

  return (
    <>
      <Style />
      <div className={prefixCls}>
        <div className={`${prefixCls}-content`}>
          <div className={`${prefixCls}-title`}>任务可能还没完成</div>
          <div className={`${prefixCls}-description`}>
            {data.reason || "我可以继续执行上一步任务。"}
          </div>
        </div>
        <div className={`${prefixCls}-actions`}>
          <Button
            size="small"
            onClick={() => {
              emit({
                type: "handlePostTurnValidationDismiss",
                data: { validation_id: data.id },
              });
            }}
          >
            不继续
          </Button>
          <Button
            size="small"
            type="primary"
            onClick={() => {
              emit({
                type: "handlePostTurnValidationContinue",
                data: { validation_id: data.id },
              });
            }}
          >
            继续执行
          </Button>
        </div>
      </div>
    </>
  );
}
