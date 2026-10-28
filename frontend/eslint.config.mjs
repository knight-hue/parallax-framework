import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';

/** Next 16 的 eslint-config-next 直接导出 flat config，
 *  不再需要旧式的 FlatCompat 包装（那套在 ESLint 9 下会因循环引用而崩）。 */
const config = [
  { ignores: ['.next/**', 'node_modules/**', 'next-env.d.ts', '.tmp-test/**'] },
  ...nextVitals,
  ...nextTypescript,
];

export default config;
