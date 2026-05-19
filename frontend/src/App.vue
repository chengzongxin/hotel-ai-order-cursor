<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

type Role = 'user' | 'assistant'

interface ChatMessage {
  id: number
  role: Role
  content: string
  time: string
}

interface PreOrder {
  roomNumber: string | null
  product: string | null
  fault: string | null
  area: string | null
  urgency: 'low' | 'medium' | 'high' | 'urgent' | null
}

const sessionId = ref(localStorage.getItem('repair_voice_session_id') || crypto.randomUUID())
const inputText = ref('')
const isListening = ref(false)
const isSending = ref(false)
const errorMessage = ref('')
const chatBodyRef = ref<HTMLElement | null>(null)

const messages = ref<ChatMessage[]>([
  {
    id: 1,
    role: 'assistant',
    content: '您好，我是维修下单助手。请按住麦克风说出房号和故障。',
    time: currentTime(),
  },
])

const preOrder = ref<PreOrder>({
  roomNumber: null,
  product: null,
  fault: null,
  area: null,
  urgency: null,
})

const historySessions = ref([
  { id: '1208', title: '1208 空调不制冷', status: '待确认', time: '09:42' },
  { id: '0816', title: '0816 水龙头漏水', status: '已派单', time: '昨天' },
  { id: '0321', title: '0321 门锁打不开', status: '已完成', time: '周日' },
])

localStorage.setItem('repair_voice_session_id', sessionId.value)

const orderCompleteness = computed(() => {
  const values = Object.values(preOrder.value)
  const filledCount = values.filter(Boolean).length
  return Math.round((filledCount / values.length) * 100)
})

const canSubmit = computed(() => {
  return Boolean(preOrder.value.roomNumber && preOrder.value.product && preOrder.value.fault)
})

function currentTime() {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date())
}

function appendMessage(role: Role, content: string) {
  messages.value.push({
    id: Date.now() + Math.floor(Math.random() * 1000),
    role,
    content,
    time: currentTime(),
  })

  nextTick(() => {
    chatBodyRef.value?.scrollTo({
      top: chatBodyRef.value.scrollHeight,
      behavior: 'smooth',
    })
  })
}

function inferPreOrder(text: string) {
  // 前端只做轻量预览，真实抽取仍应以后端 Agent 为准。
  const roomMatch = text.match(/(\d{3,5}|[A-Z]栋\d{2,5})/)
  if (roomMatch) preOrder.value.roomNumber = roomMatch[1]

  const productWords = ['空调', '电视', '水龙头', '门锁', '洗碗机', '打印机', '马桶', '窗帘']
  const product = productWords.find((word) => text.includes(word))
  if (product) preOrder.value.product = product

  const faultWords = ['不制冷', '漏水', '打不开', '不亮', '卡纸', '堵塞', '不通电', '噪音大']
  const fault = faultWords.find((word) => text.includes(word))
  if (fault) preOrder.value.fault = fault

  const areaWords = ['卫生间', '卧室', '客厅', '走廊', '会议室', '厨房', '大堂']
  const area = areaWords.find((word) => text.includes(word))
  if (area) preOrder.value.area = area

  if (/马上|很急|危险|漏电|严重/.test(text)) {
    preOrder.value.urgency = 'urgent'
  } else if (/尽快|比较急/.test(text)) {
    preOrder.value.urgency = 'high'
  } else if (/不急|有空/.test(text)) {
    preOrder.value.urgency = 'low'
  } else if (!preOrder.value.urgency) {
    preOrder.value.urgency = 'medium'
  }
}

async function sendMessage(text = inputText.value) {
  const content = text.trim()
  if (!content || isSending.value) return

  errorMessage.value = ''
  inputText.value = ''
  inferPreOrder(content)
  appendMessage('user', content)
  isSending.value = true

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        message: content,
      }),
    })

    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`)
    }

    const data = await response.json()
    if (data.session_id) {
      sessionId.value = data.session_id
      localStorage.setItem('repair_voice_session_id', data.session_id)
    }
    appendMessage('assistant', data.answer || '我已收到，会继续为您处理。')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '网络请求失败'
    appendMessage('assistant', '后端暂时不可用，我先帮您保留这条预下单信息。')
  } finally {
    isSending.value = false
  }
}

function toggleListening() {
  if (isListening.value) {
    isListening.value = false
    return
  }

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!Recognition) {
    errorMessage.value = '当前浏览器不支持语音识别，请使用文字输入。'
    return
  }

  const recognition = new Recognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = false
  recognition.maxAlternatives = 1
  isListening.value = true

  recognition.onresult = (event: SpeechRecognitionEvent) => {
    const transcript = event.results[0]?.[0]?.transcript || ''
    inputText.value = transcript
    sendMessage(transcript)
  }

  recognition.onerror = () => {
    errorMessage.value = '语音识别失败，请再试一次。'
  }

  recognition.onend = () => {
    isListening.value = false
  }

  recognition.start()
}

function resetOrder() {
  preOrder.value = {
    roomNumber: null,
    product: null,
    fault: null,
    area: null,
    urgency: null,
  }
}
</script>

<template>
  <main class="grain relative min-h-screen overflow-hidden bg-ink text-porcelain">
    <div class="absolute left-[-12rem] top-[-12rem] h-[34rem] w-[34rem] rounded-full bg-signal/20 blur-3xl"></div>
    <div class="absolute bottom-[-18rem] right-[-10rem] h-[40rem] w-[40rem] rounded-full bg-copper/20 blur-3xl"></div>

    <section class="relative z-10 mx-auto grid min-h-screen max-w-7xl gap-6 px-5 py-6 lg:grid-cols-[1.25fr_0.75fr]">
      <div class="flex min-h-[calc(100vh-3rem)] flex-col rounded-[2rem] border border-white/10 bg-white/[0.06] p-5 shadow-2xl backdrop-blur-xl">
        <header class="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5">
          <div>
            <p class="text-xs uppercase tracking-[0.45em] text-signal/80">Voice Repair Desk</p>
            <h1 class="mt-3 font-display text-4xl font-semibold tracking-tight md:text-5xl">
              AI 语音维修下单
            </h1>
          </div>
          <div class="rounded-full border border-signal/30 bg-signal/10 px-4 py-2 text-sm text-signal">
            Session {{ sessionId.slice(0, 8) }}
          </div>
        </header>

        <div ref="chatBodyRef" class="mt-5 flex-1 space-y-4 overflow-y-auto pr-2">
          <article
            v-for="message in messages"
            :key="message.id"
            class="flex"
            :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-[82%] rounded-[1.5rem] px-5 py-4 shadow-lg"
              :class="
                message.role === 'user'
                  ? 'bg-signal text-ink'
                  : 'border border-white/10 bg-black/20 text-porcelain'
              "
            >
              <p class="whitespace-pre-wrap leading-7">{{ message.content }}</p>
              <p class="mt-2 text-right text-xs opacity-60">{{ message.time }}</p>
            </div>
          </article>
        </div>

        <div class="mt-5 rounded-[1.75rem] border border-white/10 bg-black/25 p-4">
          <div class="mb-4 flex items-center justify-center gap-2" :class="{ 'opacity-100': isListening, 'opacity-30': !isListening }">
            <span v-for="bar in 5" :key="bar" class="voice-bar h-10 w-2 rounded-full bg-signal"></span>
          </div>

          <div class="grid gap-3 md:grid-cols-[auto_1fr_auto]">
            <button
              class="group relative h-20 w-20 rounded-full border border-signal/40 bg-signal/15 shadow-glow transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-60"
              :class="{ 'bg-signal text-ink': isListening }"
              :disabled="isSending"
              @click="toggleListening"
            >
              <span class="absolute inset-2 rounded-full border border-white/20"></span>
              <span class="relative text-3xl">{{ isListening ? '■' : '🎙' }}</span>
            </button>

            <textarea
              v-model="inputText"
              class="min-h-20 resize-none rounded-[1.25rem] border border-white/10 bg-white/[0.06] px-4 py-3 text-base outline-none transition placeholder:text-white/35 focus:border-signal/60"
              placeholder="也可以输入：1208 房间空调不制冷，比较急"
              @keydown.enter.prevent="sendMessage()"
            ></textarea>

            <button
              class="rounded-[1.25rem] bg-copper px-6 py-3 font-semibold text-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isSending || !inputText.trim()"
              @click="sendMessage()"
            >
              {{ isSending ? '发送中' : '发送' }}
            </button>
          </div>

          <p v-if="errorMessage" class="mt-3 text-sm text-copper">{{ errorMessage }}</p>
        </div>
      </div>

      <aside class="grid gap-6">
        <section class="rounded-[2rem] border border-white/10 bg-porcelain p-5 text-ink shadow-2xl">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-xs uppercase tracking-[0.35em] text-copper">Draft Order</p>
              <h2 class="mt-2 font-display text-3xl font-semibold">预下单卡片</h2>
            </div>
            <div class="rounded-full bg-ink px-3 py-1 text-sm text-porcelain">{{ orderCompleteness }}%</div>
          </div>

          <div class="mt-5 h-2 overflow-hidden rounded-full bg-ink/10">
            <div class="h-full rounded-full bg-copper transition-all" :style="{ width: `${orderCompleteness}%` }"></div>
          </div>

          <dl class="mt-6 grid gap-3">
            <div class="rounded-2xl bg-ink/[0.06] p-4">
              <dt class="text-xs text-ink/50">房号</dt>
              <dd class="mt-1 text-lg font-semibold">{{ preOrder.roomNumber || '待识别' }}</dd>
            </div>
            <div class="rounded-2xl bg-ink/[0.06] p-4">
              <dt class="text-xs text-ink/50">商品/设备</dt>
              <dd class="mt-1 text-lg font-semibold">{{ preOrder.product || '待识别' }}</dd>
            </div>
            <div class="rounded-2xl bg-ink/[0.06] p-4">
              <dt class="text-xs text-ink/50">故障</dt>
              <dd class="mt-1 text-lg font-semibold">{{ preOrder.fault || '待识别' }}</dd>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-2xl bg-ink/[0.06] p-4">
                <dt class="text-xs text-ink/50">区域</dt>
                <dd class="mt-1 font-semibold">{{ preOrder.area || '待补充' }}</dd>
              </div>
              <div class="rounded-2xl bg-ink/[0.06] p-4">
                <dt class="text-xs text-ink/50">紧急度</dt>
                <dd class="mt-1 font-semibold">{{ preOrder.urgency || '待判断' }}</dd>
              </div>
            </div>
          </dl>

          <div class="mt-6 grid grid-cols-2 gap-3">
            <button
              class="rounded-2xl bg-ink px-4 py-3 font-semibold text-porcelain disabled:opacity-40"
              :disabled="!canSubmit"
            >
              确认预下单
            </button>
            <button class="rounded-2xl border border-ink/15 px-4 py-3 font-semibold" @click="resetOrder">
              清空
            </button>
          </div>
        </section>

        <section class="rounded-[2rem] border border-white/10 bg-white/[0.06] p-5 backdrop-blur-xl">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs uppercase tracking-[0.35em] text-signal/70">History</p>
              <h2 class="mt-2 font-display text-3xl font-semibold">历史对话</h2>
            </div>
            <span class="rounded-full border border-white/10 px-3 py-1 text-sm text-white/60">
              {{ historySessions.length }} 条
            </span>
          </div>

          <div class="mt-5 space-y-3">
            <button
              v-for="item in historySessions"
              :key="item.id"
              class="w-full rounded-2xl border border-white/10 bg-black/20 p-4 text-left transition hover:border-signal/40 hover:bg-signal/10"
            >
              <div class="flex items-center justify-between gap-3">
                <p class="font-semibold">{{ item.title }}</p>
                <span class="text-xs text-white/45">{{ item.time }}</span>
              </div>
              <p class="mt-2 text-sm text-signal/75">{{ item.status }}</p>
            </button>
          </div>
        </section>
      </aside>
    </section>
  </main>
</template>
