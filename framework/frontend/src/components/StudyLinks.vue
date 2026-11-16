<template>
  <section class="study-links" aria-label="学习入口"><router-link to="/student/chapter-bank"><strong>客观题库</strong><span>按章节练习，或查看全部题目和答对记录</span></router-link><router-link to="/student/lab-topics"><strong>实验专题</strong><span>六个专题，结合站场观察完成作答</span></router-link><router-link to="/student/simulation-console"><strong>标准站仿真</strong><span>自由操作进路、道岔、行车和设备故障</span></router-link></section>
</template>
<style scoped>
.study-links{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-top:26px}.study-links a{display:block;padding:24px;background:white;border:1px solid #e1e8ef;border-top:3px solid #c6aa70;border-radius:8px}.study-links strong{display:block;font-size:18px;font-weight:500;margin-bottom:13px}.study-links span{font-size:13px;line-height:1.8;color:#708094}.study-links a:hover{border-color:#a4c7dd}@media(max-width:750px){.study-links{grid-template-columns:1fr;gap:12px}.study-links a{padding:20px}}
</style>
