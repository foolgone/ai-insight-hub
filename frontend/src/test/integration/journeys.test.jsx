import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AppRoutes } from '../../router'
import { renderWithProviders } from '../utils'
import { useAuthStore } from '../../stores/authStore'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { login } from '../../api/auth'
import { listDataSources } from '../../api/datasources'
import { cancelTask, listTasks } from '../../api/tasks'
import { listCleanedData } from '../../api/cleaning'
import { listQualityResults } from '../../api/quality'
import { createFaq, listFaq } from '../../api/knowledge'
import { createReport, listReports } from '../../api/reports'

vi.mock('../../api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))
vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))
vi.mock('../../api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  cancelTask: vi.fn(),
  retryTask: vi.fn(),
}))
vi.mock('../../api/cleaning', () => ({
  startCleaning: vi.fn(),
  listCleanedData: vi.fn(),
  getCleanedData: vi.fn(),
}))
vi.mock('../../api/quality', () => ({
  triggerQuality: vi.fn(),
  listQualityResults: vi.fn(),
  reviewQuality: vi.fn(),
}))
vi.mock('../../api/knowledge', () => ({
  listFaq: vi.fn(),
  searchKnowledge: vi.fn(),
  listGaps: vi.fn(),
  extractKnowledge: vi.fn(),
  createFaq: vi.fn(),
  updateFaq: vi.fn(),
  deleteFaq: vi.fn(),
}))
vi.mock('../../api/reports', () => ({
  listReports: vi.fn(),
  createReport: vi.fn(),
  getReport: vi.fn(),
  deleteReport: vi.fn(),
  downloadReport: vi.fn(),
}))

const USER = { id: 'u1', email: 'a@example.com', name: '张三', role: 'user' }
const VIEWER = { id: 'u2', email: 'v@example.com', name: '李四', role: 'viewer' }

const TASK = {
  id: 'task-1234-abcdef',
  task_type: 'clean',
  status: 'running',
  progress: 45,
  created_at: '2026-10-25T10:00:00Z',
}
const QUALITY = {
  id: 'q-1',
  data_id: 'cd-1',
  overall_score: 82,
  needs_review: true,
  dimensions: { accuracy: { score: 90, issues: [] } },
  created_at: '2026-10-25T10:00:00Z',
}
const FAQ = {
  id: 'f-1',
  question: '如何退款？',
  answer: '7 天内可退。',
  tags: [],
  source: 'manual',
}
const REPORT = {
  id: 'r-1',
  title: '质量分析报告-20261025',
  report_type: 'quality',
  format: 'markdown',
  status: 'completed',
  created_at: '2026-10-25T10:00:00Z',
}

function renderAt(path) {
  return renderWithProviders(<AppRoutes />, { route: path })
}

function loginAs(user) {
  useAuthStore.setState({ user, hydrated: true })
}

describe('页面级集成（F-502）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useAuthStore.setState({ user: null, hydrated: true })
    useDatasourceStore.setState({ currentId: 'ds-1' })

    login.mockResolvedValue({ user: USER, access_token: 'a', refresh_token: 'r' })
    listDataSources.mockResolvedValue({ items: [], pagination: { total: 0 } })
    listTasks.mockResolvedValue({ items: [], pagination: { total: 0 } })
    listCleanedData.mockResolvedValue({ items: [], pagination: { total: 0 } })
    listQualityResults.mockResolvedValue({
      items: [],
      pagination: { total: 0 },
      summary: { total: 0, avg_overall_score: 0, needs_review_count: 0 },
    })
    listFaq.mockResolvedValue({
      items: [],
      pagination: { page: 1, has_next: false, total: 0 },
    })
    listReports.mockResolvedValue({ items: [], pagination: { total: 0 } })
    cancelTask.mockResolvedValue({ status: 'cancelled' })
    createFaq.mockResolvedValue({ id: 'f-2' })
    createReport.mockResolvedValue({ id: 'r-2' })
  })

  afterEach(() => {
    useAuthStore.setState({ user: null })
    useDatasourceStore.setState({ currentId: null })
    localStorage.clear()
  })

  it('链路 1：登录成功进入 Dashboard', async () => {
    const user = userEvent.setup()
    renderAt('/login')

    await user.type(await screen.findByLabelText('邮箱'), 'a@example.com')
    await user.type(screen.getByLabelText('密码'), 'secret123')
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(
      await screen.findByRole('heading', { name: 'Dashboard' }, { timeout: 6000 })
    ).toBeInTheDocument()
    expect(login).toHaveBeenCalledWith({ email: 'a@example.com', password: 'secret123' })
  })

  it('链路 2：未登录访问业务路由跳转登录页', async () => {
    renderAt('/data-sources')

    expect(
      await screen.findByRole('heading', { name: '欢迎使用 AI Insight Hub' })
    ).toBeInTheDocument()
  })

  it('链路 3：数据源列表 → 打开新建 Drawer', async () => {
    loginAs(USER)
    listDataSources.mockResolvedValue({
      items: [
        {
          id: 'ds-1',
          name: '客服1月',
          type: 'csv',
          status: 'ready',
          created_at: '2026-10-25T10:00:00Z',
        },
      ],
      pagination: { total: 1 },
    })
    const user = userEvent.setup()
    renderAt('/data-sources')

    expect(await screen.findByText('客服1月')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '新建数据源' }))

    expect(await screen.findByRole('dialog', { name: '新建数据源' })).toBeInTheDocument()
  })

  it('链路 4：清洗任务列表 → 取消任务', async () => {
    loginAs(USER)
    listTasks.mockResolvedValue({ items: [TASK], pagination: { total: 1 } })
    const user = userEvent.setup()
    renderAt('/data-cleaning')

    expect(await screen.findByText('task-123')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '取消' }))

    await waitFor(() => expect(cancelTask).toHaveBeenCalledWith(TASK.id, expect.anything()))
  })

  it('链路 5：质量评估列表 → 详情页', async () => {
    loginAs(USER)
    listQualityResults.mockResolvedValue({
      items: [QUALITY],
      pagination: { total: 1 },
      summary: { total: 1, avg_overall_score: 82, needs_review_count: 1 },
    })
    const user = userEvent.setup()
    renderAt('/quality-assessment')

    await user.click(await screen.findByRole('link', { name: '查看详情' }))

    expect(await screen.findByRole('heading', { name: '评估详情' })).toBeInTheDocument()
    expect(await screen.findByRole('img', { name: '质量分 82' })).toBeInTheDocument()
  })

  it('链路 6：知识库 → 新建 FAQ 保存', async () => {
    loginAs(USER)
    listFaq.mockResolvedValue({
      items: [FAQ],
      pagination: { page: 1, has_next: false, total: 1 },
    })
    const user = userEvent.setup()
    renderAt('/knowledge-base')

    await screen.findByRole('heading', { name: '如何退款？' }, { timeout: 8000 })
    await user.click(screen.getByRole('button', { name: '新建条目' }))
    const dialog = await screen.findByRole('dialog', { name: '新建知识条目' })
    await user.type(within(dialog).getByLabelText(/问题/), '如何换货？')
    await user.type(within(dialog).getByLabelText(/答案/), '7 天内可换。')
    await user.click(within(dialog).getByRole('button', { name: '保存' }))

    await waitFor(() =>
      expect(createFaq).toHaveBeenCalledWith(
        'ds-1',
        expect.objectContaining({ question: '如何换货？', answer: '7 天内可换。' })
      )
    )
  })

  it('链路 7：报告中心 → 生成报告', async () => {
    loginAs(USER)
    listReports.mockResolvedValue({ items: [REPORT], pagination: { total: 1 } })
    const user = userEvent.setup()
    renderAt('/reports')

    await screen.findByRole('heading', { name: REPORT.title })
    await user.click(screen.getByRole('button', { name: '生成报告' }))
    const dialog = await screen.findByRole('dialog', { name: '生成报告' })
    await user.click(within(dialog).getByRole('button', { name: '生成报告' }))

    await waitFor(() =>
      expect(createReport).toHaveBeenCalledWith(
        'ds-1',
        expect.objectContaining({ report_type: 'quality', format: 'markdown' })
      )
    )
  })

  it('链路 8：viewer 角色无新建数据源入口', async () => {
    loginAs(VIEWER)
    renderAt('/data-sources')

    expect(await screen.findByRole('heading', { name: '数据源管理' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '新建数据源' })).toBeNull()
  })
})
