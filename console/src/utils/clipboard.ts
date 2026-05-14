type ClipboardPolicy = {
  allowsFeature?: (feature: string) => boolean;
};

type ClipboardAwareDocument = Document & {
  permissionsPolicy?: ClipboardPolicy;
  featurePolicy?: ClipboardPolicy;
};

const CLIPBOARD_WRITE_FEATURE = "clipboard-write";
const COPY_COMMAND = "copy";

function allowsClipboardWriteByPolicy(): boolean {
  const doc = document as ClipboardAwareDocument;
  const policy = doc.permissionsPolicy ?? doc.featurePolicy;
  if (typeof policy?.allowsFeature !== "function") {
    return true;
  }

  try {
    return policy.allowsFeature(CLIPBOARD_WRITE_FEATURE);
  } catch {
    return true;
  }
}

function canUseClipboardApi(): boolean {
  return Boolean(
    window.isSecureContext &&
      navigator.clipboard?.writeText &&
      allowsClipboardWriteByPolicy(),
  );
}

function copyByExecCommand(text: string): boolean {
  if (typeof document.execCommand !== "function") {
    return false;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "-9999px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);

  try {
    textarea.focus();
    textarea.select();
    return document.execCommand(COPY_COMMAND);
  } finally {
    document.body.removeChild(textarea);
  }
}

export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false;

  if (canUseClipboardApi()) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return copyByExecCommand(text);
    }
  }

  return copyByExecCommand(text);
}
