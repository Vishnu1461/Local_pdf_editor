import { useEffect, useRef } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";

function Thumbnail({ pdf, index, active, onClick }: { pdf: PDFDocumentProxy; index: number; active: boolean; onClick: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let cancelled = false;
    let task: { cancel: () => void } | null = null;
    pdf.getPage(index + 1).then((page) => {
      if (cancelled) return;
      const base = page.getViewport({ scale: 1 });
      const view = page.getViewport({ scale: 108 / base.width });
      const canvas = canvasRef.current;
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(view.width * dpr);
      canvas.height = Math.floor(view.height * dpr);
      canvas.style.width = `${view.width}px`;
      canvas.style.height = `${view.height}px`;
      const context = canvas.getContext("2d");
      if (!context) return;
      const render = page.render({
        canvasContext: context,
        canvas,
        viewport: view,
        transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
      });
      task = render;
      render.promise.catch(() => undefined);
    });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [pdf, index]);

  return (
    <button className={`thumb${active ? " is-active" : ""}`} onClick={onClick} title={`Page ${index + 1}`}>
      <canvas ref={canvasRef} />
      <span className="thumb-label">{index + 1}</span>
    </button>
  );
}

interface Props {
  pdf: PDFDocumentProxy;
  pageCount: number;
  currentPage: number;
  onGoPage: (index: number) => void;
  documentName: string;
  fieldCount: number;
  templateName: string | null;
}

export function Sidebar({ pdf, pageCount, currentPage, onGoPage, documentName, fieldCount, templateName }: Props) {
  return (
    <aside className="rail">
      <div className="rail-doc">
        <div className="rail-name" title={documentName}>
          {documentName}
        </div>
        <div className="rail-meta">
          {pageCount} pages · {fieldCount} fields
        </div>
        {templateName && <div className="rail-template">{templateName}</div>}
      </div>
      <div className="thumbs">
        {Array.from({ length: pageCount }, (_, index) => (
          <Thumbnail
            key={index}
            pdf={pdf}
            index={index}
            active={index === currentPage}
            onClick={() => onGoPage(index)}
          />
        ))}
      </div>
    </aside>
  );
}
