import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Parallax 控制台',
  description: '抗从众的多智能体证据装配框架 —— 审查进度、Claim 账本与覆盖率矩阵',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
