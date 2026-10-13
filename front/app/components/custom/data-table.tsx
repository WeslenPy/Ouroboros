import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table"
import { useState } from "react"
import { IconArrowsSort, IconSortAscending, IconSortDescending } from "@tabler/icons-react"

import { Skeleton } from "@/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/ui/table"
import { cn } from "~/lib/utils"
import { EmptyState, ErrorState, LoadMore } from "./states"

/**
 * Tabela tanstack para listas paginadas por cursor. Ordenação é local (só o que foi carregado):
 * a API ordena por chave e não aceita parâmetro de ordenação.
 */
export function DataTable<T>({
  columns,
  data,
  loading,
  error,
  onRetry,
  hasMore,
  onLoadMore,
  onRowClick,
  className,
  skeletonRows = 8,
}: {
  columns: ColumnDef<T, any>[]
  data: T[]
  loading?: boolean
  error?: Error
  onRetry?: () => void
  hasMore?: boolean
  onLoadMore?: () => void
  onRowClick?: (row: T) => void
  className?: string
  skeletonRows?: number
}) {
  const [sorting, setSorting] = useState<SortingState>([])
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (error && !data.length) return <ErrorState error={error} onRetry={onRetry} />

  return (
    <div className={className}>
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader className="sticky top-0 bg-muted/60">
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id}>
                {group.headers.map((header) => {
                  const sortable = header.column.getCanSort()
                  const dir = header.column.getIsSorted()
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        "text-xs whitespace-nowrap",
                        sortable && "cursor-pointer select-none",
                        (header.column.columnDef.meta as { className?: string })?.className,
                      )}
                      onClick={sortable ? header.column.getToggleSortingHandler() : undefined}
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {sortable &&
                          (dir === "asc" ? (
                            <IconSortAscending className="size-3.5" />
                          ) : dir === "desc" ? (
                            <IconSortDescending className="size-3.5" />
                          ) : (
                            <IconArrowsSort className="size-3.5 opacity-30" />
                          ))}
                      </span>
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className={cn(onRowClick && "cursor-pointer")}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={(cell.column.columnDef.meta as { className?: string })?.className}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
            {loading &&
              !data.length &&
              Array.from({ length: skeletonRows }).map((_, i) => (
                <TableRow key={`s${i}`}>
                  {columns.map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full max-w-40" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
          </TableBody>
        </Table>
        {!loading && !data.length && <EmptyState className="rounded-none border-none" />}
      </div>
      {onLoadMore && (
        <LoadMore
          hasMore={!!hasMore}
          loading={!!loading}
          onClick={onLoadMore}
          count={data.length}
        />
      )}
    </div>
  )
}
