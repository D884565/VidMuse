const TOKEN_KEY = 'admin_token'
const USER_KEY = 'admin_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  return localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getUserInfo() {
  const user = localStorage.getItem(USER_KEY)
  return user ? JSON.parse(user) : null
}

export function setUserInfo(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function isLoggedIn() {
  return !!getToken()
}
