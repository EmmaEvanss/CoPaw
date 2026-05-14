import { copyToClipboard } from "@/utils/clipboard";

const COPY_FAILED_MESSAGE = "复制失败";

export async function copy(text: string): Promise<void> {
  const copied = await copyToClipboard(text);
  if (!copied) {
    throw new Error(COPY_FAILED_MESSAGE);
  }
}
