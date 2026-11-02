const egp = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export const money = (n: number) => `${egp.format(n)} EGP`;
export const price = (n: number) => egp.format(n);
export const count = (n: number) => whole.format(n);

/** Signed percent with a direction glyph, so gain/loss never depends on color. */
export const pct = (n: number) => `${n > 0 ? "▲ +" : n < 0 ? "▼ −" : ""}${Math.abs(n).toFixed(2)}%`;
export const signedMoney = (n: number) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${egp.format(Math.abs(n))}`;
export const tone = (n: number) => (n > 0 ? "up" : n < 0 ? "down" : "flat");

export const shortDate = (iso: string) =>
  new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
export const longDate = (iso: string) =>
  new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", {
    weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });

/** Arabic company names for the mock universe (display only). */
export const ARABIC: Record<string, string> = {
  COMI: "البنك التجاري الدولي",
  HRHO: "إي اف چي القابضة",
  TMGH: "مجموعة طلعت مصطفى",
  EAST: "الشرقية للدخان",
  SWDY: "السويدي إليكتريك",
  FWRY: "فوري",
  ETEL: "المصرية للاتصالات",
  ABUK: "أبوقير للأسمدة",
};
