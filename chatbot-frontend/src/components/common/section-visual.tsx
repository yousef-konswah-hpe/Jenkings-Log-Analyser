import Image from "next/image";

type SectionVisualProps = {
  src: string;
  alt: string;
};

export function SectionVisual({ src, alt }: SectionVisualProps) {
  return (
    <div className="mb-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-950">
      <Image
        src={src}
        alt={alt}
        width={760}
        height={360}
        className="h-auto w-full"
      />
    </div>
  );
}
