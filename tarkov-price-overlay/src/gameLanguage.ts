import type { GameLang, Lang } from "./i18n";

/** Resolve the EFT client language independently from the UI language. */
export function resolveGameLang(uiLang: Lang, gameLang?: GameLang): GameLang {
  if (gameLang) return gameLang;
  return uiLang === "zh" ? "en" : uiLang;
}
