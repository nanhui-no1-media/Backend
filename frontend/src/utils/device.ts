/** 手机设备判定（按 UA）：手机访问站点首页时直接进入手机版（/#/m）。
 *
 * 命中 iPhone / Android / Windows Phone 等常见手机 UA；桌面浏览器以及手机浏览器
 * 「请求桌面站点」模式（UA 不再含手机特征）不会命中。
 */
export function isMobileDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iPhone|iPod|Android|Windows Phone|BlackBerry|Opera Mini|IEMobile|Mobile/i.test(
    navigator.userAgent,
  );
}
