const KEY = "examBoardPrefs";
const VERSION = 2;

export type ExamBoardPrefs = {
  mascot: boolean;
  sound: boolean;
  voice: boolean;
};

const DEFAULTS: ExamBoardPrefs = { mascot: true, sound: true, voice: false };

export function loadExamBoardPrefs(): ExamBoardPrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw);
    const migrated = parsed.v === VERSION;
    return {
      mascot: parsed.mascot !== false,
      sound: parsed.sound !== false,
      voice: migrated ? parsed.voice === true : false,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveExamBoardPrefs(prefs: ExamBoardPrefs): void {
  localStorage.setItem(KEY, JSON.stringify({ v: VERSION, ...prefs }));
  window.dispatchEvent(new CustomEvent("exam-board-prefs"));
}

export function applyExamBoardMascotClass(show: boolean): void {
  document.body.classList.toggle("exam-board-hide-mascot", !show);
}
