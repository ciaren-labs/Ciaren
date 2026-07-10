import {
  Cloud,
  Database,
  FlaskConical,
  FolderOpen,
  Globe,
  HardDrive,
  Snowflake,
  type LucideIcon,
} from "lucide-react";
import {
  siDuckdb,
  siGooglecloudstorage,
  siMongodb,
  siMysql,
  siPostgresql,
  siSnowflake,
  siSqlite,
  type SimpleIcon,
} from "simple-icons";
import { cn } from "@/lib/utils";

// ─── Brand icon metadata ──────────────────────────────────────────────────────

type ProviderMeta = {
  /** simple-icons SVG object. null = use lucideIcon instead. */
  brandIcon: SimpleIcon | null;
  /** Hex color (without #) for both the brand icon fill and the bg tint.
   *  Overrides brandIcon.hex when the brand color has poor contrast on white. */
  color: string;
  lucideIcon: LucideIcon;
  description: string;
};

const PROVIDER_META: Record<string, ProviderMeta> = {
  postgresql: {
    brandIcon: siPostgresql,
    color: siPostgresql.hex,
    lucideIcon: Database,
    description: "Open-source relational database",
  },
  mysql: {
    brandIcon: siMysql,
    color: siMysql.hex,
    lucideIcon: Database,
    description: "Popular open-source database",
  },
  sqlite: {
    brandIcon: siSqlite,
    color: siSqlite.hex,
    lucideIcon: HardDrive,
    description: "Lightweight file-based database",
  },
  mssql: {
    brandIcon: null,
    color: "7c3aed",
    lucideIcon: Database,
    description: "Microsoft SQL Server",
  },
  duckdb: {
    brandIcon: siDuckdb,
    // FFF000 (pure yellow) is invisible on white; use a darker amber instead.
    color: "c8a000",
    lucideIcon: HardDrive,
    description: "In-process analytics database",
  },
  snowflake: {
    brandIcon: siSnowflake,
    color: siSnowflake.hex,
    lucideIcon: Snowflake,
    description: "Cloud data warehouse",
  },
  mongodb: {
    brandIcon: siMongodb,
    color: siMongodb.hex,
    lucideIcon: Database,
    description: "Document-oriented NoSQL database",
  },
  // Amazon/Microsoft don't have public simple-icons due to trademark policy.
  // Use Lucide icons with brand-appropriate colors instead.
  s3: {
    brandIcon: null,
    color: "FF9900",
    lucideIcon: Cloud,
    description: "AWS S3 or any S3-compatible store",
  },
  azure_blob: {
    brandIcon: null,
    color: "0078D4",
    lucideIcon: Cloud,
    description: "Microsoft Azure Blob Storage",
  },
  gcs: {
    brandIcon: siGooglecloudstorage,
    // AECBFA is too light; use Google's primary blue.
    color: "4285F4",
    lucideIcon: Cloud,
    description: "Google Cloud Storage",
  },
  local: {
    brandIcon: null,
    color: "64748b",
    lucideIcon: FolderOpen,
    description: "Local folder on the server",
  },
  rest_api: {
    brandIcon: null,
    color: "0EA5E9",
    lucideIcon: Globe,
    description: "Any REST / HTTP API returning JSON or CSV",
  },
  mlflow: {
    brandIcon: null,
    color: "0194E2",
    lucideIcon: FlaskConical,
    description: "MLflow experiment & model tracking",
  },
};

export function getProviderMeta(name: string): ProviderMeta {
  return (
    PROVIDER_META[name] ?? {
      brandIcon: null,
      color: "64748b",
      lucideIcon: Database,
      description: "",
    }
  );
}

/** Colored icon badge — shared between the picker cards and the connection list. */
export function ProviderIconBadge({
  name,
  size = "md",
}: {
  name: string;
  size?: "sm" | "md" | "lg";
}) {
  const meta = getProviderMeta(name);
  const fill = `#${meta.color}`;
  const bg = `${fill}18`; // ~10% opacity tint
  const iconCls = size === "sm" ? "h-4 w-4" : size === "lg" ? "h-9 w-9" : "h-5 w-5";
  const padCls = size === "sm" ? "p-1.5" : size === "lg" ? "p-3.5" : "p-2";

  return (
    <div
      className={cn("shrink-0", size === "lg" ? "rounded-2xl" : "rounded-lg", padCls)}
      style={{ backgroundColor: bg }}
    >
      {meta.brandIcon ? (
        <svg
          role="img"
          viewBox="0 0 24 24"
          className={iconCls}
          style={{ fill }}
          aria-label={meta.brandIcon.title}
        >
          <path d={meta.brandIcon.path} />
        </svg>
      ) : (
        <meta.lucideIcon className={iconCls} style={{ color: fill }} />
      )}
    </div>
  );
}
