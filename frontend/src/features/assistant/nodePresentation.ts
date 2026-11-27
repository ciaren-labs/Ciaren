import {
  ArrowDownWideNarrow,
  Combine,
  FileInput,
  FileOutput,
  Filter,
  GitBranch,
  Layers3,
  ListOrdered,
  SlidersHorizontal,
} from "lucide-react";
import { getNodeTypeDef } from "@/features/flows/editor/nodeCatalog";

export function nodeMark(type: string) {
  const category = getNodeTypeDef(type)?.category;
  if (category === "input") return { Icon: FileInput, color: "text-info" };
  if (category === "output") return { Icon: FileOutput, color: "text-success" };
  const icons = {
    join: Combine,
    conditionalColumn: GitBranch,
    limitRows: ListOrdered,
    sortRows: ArrowDownWideNarrow,
    filterRows: Filter,
    removeDuplicates: Layers3,
  };
  return {
    Icon: icons[type as keyof typeof icons] ?? SlidersHorizontal,
    color: "text-primary",
  };
}
