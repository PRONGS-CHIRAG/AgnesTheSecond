"use client";

import ReactMarkdown, { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const COMPONENTS: Components = {
  h1: (props) => (
    <h1
      className="mt-3 mb-2 text-lg font-semibold text-slate-900 first:mt-0"
      {...props}
    />
  ),
  h2: (props) => (
    <h2
      className="mt-3 mb-1.5 text-base font-semibold text-slate-900 first:mt-0"
      {...props}
    />
  ),
  h3: (props) => (
    <h3
      className="mt-2 mb-1 text-sm font-semibold text-slate-900 first:mt-0"
      {...props}
    />
  ),
  h4: (props) => (
    <h4
      className="mt-2 mb-1 text-sm font-semibold text-slate-800 first:mt-0"
      {...props}
    />
  ),
  p: (props) => (
    <p className="my-1.5 leading-relaxed text-slate-800 first:mt-0 last:mb-0" {...props} />
  ),
  a: (props) => (
    <a
      className="font-medium text-indigo-600 underline-offset-2 hover:underline"
      target="_blank"
      rel="noreferrer"
      {...props}
    />
  ),
  ul: (props) => (
    <ul
      className="my-1.5 list-disc space-y-0.5 pl-5 text-slate-800 marker:text-slate-400"
      {...props}
    />
  ),
  ol: (props) => (
    <ol
      className="my-1.5 list-decimal space-y-0.5 pl-5 text-slate-800 marker:text-slate-400"
      {...props}
    />
  ),
  li: (props) => <li className="leading-relaxed" {...props} />,
  strong: (props) => (
    <strong className="font-semibold text-slate-900" {...props} />
  ),
  em: (props) => <em className="italic text-slate-800" {...props} />,
  hr: () => <hr className="my-3 border-slate-200" />,
  blockquote: (props) => (
    <blockquote
      className="my-2 border-l-2 border-indigo-300 bg-indigo-50/50 px-3 py-1 text-slate-700"
      {...props}
    />
  ),
  code: ({ inline, className, children, ...rest }: {
    inline?: boolean;
    className?: string;
    children?: React.ReactNode;
  } & React.HTMLAttributes<HTMLElement>) => {
    if (inline) {
      return (
        <code
          className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-slate-800"
          {...rest}
        >
          {children}
        </code>
      );
    }
    return (
      <code
        className={`block overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100 ${className ?? ""}`}
        {...rest}
      >
        {children}
      </code>
    );
  },
  pre: (props) => <pre className="my-2" {...props} />,
  table: (props) => (
    <div className="my-2 overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full border-collapse text-sm" {...props} />
    </div>
  ),
  thead: (props) => (
    <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600" {...props} />
  ),
  tbody: (props) => <tbody className="divide-y divide-slate-100" {...props} />,
  tr: (props) => <tr className="hover:bg-slate-50/70" {...props} />,
  th: (props) => (
    <th
      className="whitespace-nowrap border-b border-slate-200 px-3 py-2 font-semibold text-slate-700"
      {...props}
    />
  ),
  td: (props) => (
    <td className="px-3 py-2 align-top text-slate-800" {...props} />
  ),
};

export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
