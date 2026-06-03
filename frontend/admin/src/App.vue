<template>
  <div class="app">
    <h1>{{ VITE_APP_TITLE }}</h1>
    <el-button type="primary">Element Plus 测试</el-button>
  </div>
</template>

<script setup>
const VITE_APP_TITLE = import.meta.env.VITE_APP_TITLE
</script>

<style scoped>
.app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}
</style>
