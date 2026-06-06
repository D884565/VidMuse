import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2 } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import CreateUserModal from '../../components/Admin/User/CreateUserModal'
import EditUserModal from '../../components/Admin/User/EditUserModal'
import { getUserList, deleteUser, createUser, updateUser } from '../../services/admin'
import { useAppStore } from '../../store/appStore'

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'username', title: '用户名' },
  { key: 'email', title: '邮箱' },
  {
    key: 'role',
    title: '角色',
    render: (role) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
      }`}>
        {role === 'admin' ? '管理员' : '普通用户'}
      </span>
    )
  },
  { key: 'createdAt', title: '注册时间' },
]

// 模拟数据
const mockUsers = [
  { id: 1, username: 'admin', email: 'admin@vidmuse.com', role: 'admin', createdAt: '2026-01-01' },
  { id: 2, username: 'user1', email: 'user1@vidmuse.com', role: 'user', createdAt: '2026-01-02' },
  { id: 3, username: 'user2', email: 'user2@vidmuse.com', role: 'user', createdAt: '2026-01-03' },
  { id: 4, username: 'user3', email: 'user3@vidmuse.com', role: 'user', createdAt: '2026-01-04' },
  { id: 5, username: 'user4', email: 'user4@vidmuse.com', role: 'user', createdAt: '2026-01-05' },
]

export default function UserManagement() {
  const [loading, setLoading] = useState(true)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const userList = useAppStore((state) => state.userList)
  const setUserList = useAppStore((state) => state.setUserList)

  const fetchUsers = async () => {
    try {
      setLoading(true)
      const data = await getUserList()
      // 假设API返回的是列表或者包含list字段的对象
      setUserList(Array.isArray(data) ? data : data?.list || [])
    } catch (error) {
      console.error('获取用户列表失败:', error)
      setUserList([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  const handleEdit = (user) => {
    setEditingUser(user)
    setEditModalOpen(true)
  }

  const handleDelete = async (userId) => {
    if (window.confirm('确定要删除这个用户吗？')) {
      try {
        await deleteUser(userId)
        fetchUsers()
      } catch (error) {
        console.error('删除用户失败:', error)
        alert('删除用户失败，请重试')
      }
    }
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-2">
      <button
        onClick={() => handleEdit(row)}
        className="p-1 text-blue-600 hover:text-blue-800"
        title="编辑"
      >
        <Edit size={16} />
      </button>
      <button
        onClick={() => handleDelete(row.id)}
        className="p-1 text-red-600 hover:text-red-800"
        title="删除"
      >
        <Trash2 size={16} />
      </button>
    </div>
  )

  return (
    <PageContainer
      title="用户管理"
      actions={
        <button
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={20} />
          <span>创建用户</span>
        </button>
      }
    >
      <Table
        columns={columns}
        data={userList}
        actions={actions}
        loading={loading}
      />

      <CreateUserModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={fetchUsers}
      />

      <EditUserModal
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        user={editingUser}
        onSuccess={fetchUsers}
      />
    </PageContainer>
  )
}

