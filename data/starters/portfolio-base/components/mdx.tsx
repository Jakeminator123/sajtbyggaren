import Image, { type ImageProps } from "next/image";
import Link from "next/link";
import { MDXRemote } from "next-mdx-remote/rsc";
import React, {
  type AnchorHTMLAttributes,
  type ComponentProps,
  type ReactNode,
} from "react";
import { highlight } from "sugar-high";

type TableData = {
  headers: string[];
  rows: string[][];
};

function textFromNode(children: ReactNode): string {
  if (typeof children === "string" || typeof children === "number") {
    return String(children);
  }

  if (Array.isArray(children)) {
    return children.map(textFromNode).join("");
  }

  return "";
}

function Table({ data }: { data: TableData }) {
  return (
    <table>
      <thead>
        <tr>
          {data.headers.map((header) => (
            <th key={header}>{header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.rows.map((row, rowIndex) => (
          <tr key={row.join("-") || rowIndex}>
            {row.map((cell, cellIndex) => (
              <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CustomLink({
  href = "",
  children,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement>) {
  if (href.startsWith("/")) {
    return (
      <Link href={href} {...props}>
        {children}
      </Link>
    );
  }

  if (href.startsWith("#")) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  }

  return (
    <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
      {children}
    </a>
  );
}

function RoundedImage({ alt, ...props }: ImageProps) {
  return <Image alt={alt} className="rounded-lg" {...props} />;
}

function Code({ children, ...props }: ComponentProps<"code">) {
  const codeHTML = highlight(String(children ?? ""));

  return <code dangerouslySetInnerHTML={{ __html: codeHTML }} {...props} />;
}

function slugify(value: string): string {
  return value
    .toString()
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/&/g, "-and-")
    .replace(/[^\w-]+/g, "")
    .replace(/--+/g, "-");
}

function createHeading(level: 1 | 2 | 3 | 4 | 5 | 6) {
  function Heading({ children }: { children: ReactNode }) {
    const slug = slugify(textFromNode(children));

    return React.createElement(
      `h${level}`,
      { id: slug },
      React.createElement("a", {
        href: `#${slug}`,
        key: `link-${slug}`,
        className: "anchor",
      }),
      children,
    );
  }

  Heading.displayName = `Heading${level}`;

  return Heading;
}

const components = {
  h1: createHeading(1),
  h2: createHeading(2),
  h3: createHeading(3),
  h4: createHeading(4),
  h5: createHeading(5),
  h6: createHeading(6),
  Image: RoundedImage,
  a: CustomLink,
  code: Code,
  Table,
};

export function CustomMDX(props: ComponentProps<typeof MDXRemote>) {
  return (
    <MDXRemote
      {...props}
      components={{ ...components, ...(props.components || {}) }}
    />
  );
}
