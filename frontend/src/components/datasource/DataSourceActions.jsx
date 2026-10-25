import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { LuEye, LuMoreHorizontal, LuPencil, LuTrash2, LuUpload } from 'react-icons/lu'

const ITEM_CLASS =
  'flex w-full cursor-pointer items-center gap-2 rounded px-3 py-2 text-sm text-gray-700 outline-none focus:bg-gray-50'

/**
 * 数据源操作菜单（F-204）：查看详情/编辑/上传/删除；viewer 只保留查看。
 * @param {{
 *   datasource: Object,
 *   canWrite?: boolean,
 *   onDetail: () => void,
 *   onEdit: () => void,
 *   onUpload: () => void,
 *   onDelete: () => void,
 * }} props
 */
export function DataSourceActions({
  datasource,
  canWrite = true,
  onDetail,
  onEdit,
  onUpload,
  onDelete,
}) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={`数据源操作：${datasource.name}`}
          className="flex h-9 w-9 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
        >
          <LuMoreHorizontal className="h-5 w-5" aria-hidden="true" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 min-w-44 rounded-md border border-gray-200 bg-white p-1 shadow-lg focus:outline-none"
        >
          <DropdownMenu.Item onSelect={onDetail} className={ITEM_CLASS}>
            <LuEye className="h-4 w-4 text-gray-400" aria-hidden="true" />
            查看详情
          </DropdownMenu.Item>

          {canWrite ? (
            <>
              <DropdownMenu.Item onSelect={onEdit} className={ITEM_CLASS}>
                <LuPencil className="h-4 w-4 text-gray-400" aria-hidden="true" />
                编辑信息
              </DropdownMenu.Item>
              <DropdownMenu.Item onSelect={onUpload} className={ITEM_CLASS}>
                <LuUpload className="h-4 w-4 text-gray-400" aria-hidden="true" />
                上传数据
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-gray-100" />
              <DropdownMenu.Item
                onSelect={onDelete}
                className="flex w-full cursor-pointer items-center gap-2 rounded px-3 py-2 text-sm text-error-600 outline-none focus:bg-error-50"
              >
                <LuTrash2 className="h-4 w-4" aria-hidden="true" />
                删除数据源
              </DropdownMenu.Item>
            </>
          ) : null}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
