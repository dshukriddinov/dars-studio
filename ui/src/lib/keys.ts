// Tekshirish ekrani klaviaturasi (FR-14). Sof funksiya: hodisa -> amal nomi.
export type KeyAction =
  | "reverse" | "pause" | "play" | "toggle" | "prevFrame" | "nextFrame" | "back1s" | "fwd1s"
  | "boundaryLeft" | "boundaryRight" | "sceneA" | "sceneB" | "approveCut" | "undo" | "redo";

export interface KeyLike {
  key: string; shiftKey?: boolean; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean; target?: EventTarget | null;
}

export function isTyping(t: EventTarget | null | undefined): boolean {
  const el = t as HTMLElement | null;
  if (!el || !el.tagName) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

export function keyToAction(e: KeyLike): KeyAction | null {
  if (isTyping(e.target) || e.altKey) return null;
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if (e.ctrlKey || e.metaKey) {
    if (k === "z") return e.shiftKey ? "redo" : "undo";
    if (k === "y") return "redo";
    return null;
  }
  switch (k) {
    case "j": return "reverse";
    case "k": return "pause";
    case " ": return "toggle";
    case "l": return "play";
    case "ArrowLeft": return e.shiftKey ? "back1s" : "prevFrame";
    case "ArrowRight": return e.shiftKey ? "fwd1s" : "nextFrame";
    case "[": return "boundaryLeft";
    case "]": return "boundaryRight";
    case "1": return "sceneA";
    case "2": return "sceneB";
    case "Enter": return "approveCut";
  }
  return null;
}
