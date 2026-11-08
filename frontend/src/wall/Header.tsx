import { useEffect, useRef, type Ref } from "react";
import QRCode from "qrcode";
import type { Theme } from "../types";

interface Props {
  title: string;
  qrUrl: string;
  theme: Theme;
  ref?: Ref<HTMLElement>;
}

export function Header({ title, qrUrl, theme, ref }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvas.current) return;
    QRCode.toCanvas(canvas.current, qrUrl, { margin: 1, width: 280, color: { dark: "#0e1230", light: "#ffffff" } }).catch(() => {});
  }, [qrUrl]);

  return (
    <header className="header" ref={ref}>
      {/* dir="auto": a Hebrew title reads right to left, punctuation included */}
      <h1 aria-label={title} dir="auto">{theme.renderTitle(title)}</h1>
      <div className="qr">
        <canvas ref={canvas} aria-label="QR code for joining the photo album" />
        <span>{theme.qrCaption}</span>
      </div>
    </header>
  );
}
