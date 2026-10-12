"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/**
 * The site's languages. English is the source; Simplified Chinese is the translation.
 * The choice is remembered in this browser and sets the page's `lang` attribute.
 */
export type Lang = "en" | "zh";
export const LANGS: { code: Lang; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "zh", label: "中文" },
];
const KEY = "h402.lang";

type Entry = { en: string; zh: string };

const STRINGS: Record<string, Entry> = {
  // Navigation
  "nav.tasks": { en: "Tasks", zh: "任务" },
  "nav.map": { en: "Map", zh: "地图" },
  "nav.docs": { en: "Docs", zh: "文档" },
  "nav.rewards": { en: "Rewards", zh: "奖励" },
  "nav.sources": { en: "Sources", zh: "来源" },
  "nav.how": { en: "How it works", zh: "运作方式" },
  "nav.board": { en: "See the board", zh: "查看任务板" },
  "nav.connect": { en: "Connect wallet", zh: "连接钱包" },
  "nav.connecting": { en: "Connecting…", zh: "连接中…" },
  "nav.earn": { en: "Start earning", zh: "开始赚取" },
  "nav.menu": { en: "Menu", zh: "菜单" },
  "nav.language": { en: "Language", zh: "语言" },

  // Live pill
  "live.live": { en: "Live", zh: "在线" },
  "live.one": { en: "1 person online", zh: "1 人在线" },
  "live.many": { en: "{n} people online", zh: "{n} 人在线" },
  "live.title": { en: "People active on H402 in the last ten minutes", zh: "过去十分钟内活跃在 H402 的人数" },

  // Hero
  "hero.title.a": { en: "Work that ", zh: "交付" },
  "hero.title.em": { en: "pays", zh: "即付" },
  "hero.title.b": { en: " on delivery", zh: "的工作" },
  "hero.sub": { en: "New tasks are posted around the clock. Real people do them in minutes and are paid the moment the work is accepted.", zh: "新任务全天候发布。真人几分钟内完成，工作一经验收即刻获得报酬。" },
  "hero.cta": { en: "See open tasks", zh: "查看开放任务" },
  "hero.trade": { en: "Trade on Axiom", zh: "在 Axiom 交易" },
  "hero.copy": { en: "Copy the contract address", zh: "复制合约地址" },

  // Payments strip
  "ticker.paid": { en: "Paid on chain", zh: "链上支付" },
  "ticker.paidShort": { en: "Paid", zh: "已付" },
  "ticker.paidTo": { en: "paid to", zh: "支付给" },
  "ticker.for": { en: "for “{title}”", zh: "用于“{title}”" },
  "ticker.team": { en: "H402 team", zh: "H402 团队" },

  // Try one
  "try.label": { en: "Try one", zh: "试一试" },
  "try.title.a": { en: "See how a task ", zh: "看看任务是如何" },
  "try.title.em": { en: "works", zh: "运作的" },
  "try.desc": { en: "Answer the practice question and follow it through the same four steps every real task takes, from your answer to the reward.", zh: "回答练习题，并跟随每个真实任务都要经历的四个步骤：从你的回答到奖励。" },
  "try.practice": { en: "Practice task. Nothing is paid.", zh: "练习任务，不支付报酬。" },
  "try.reward": { en: "Reward", zh: "奖励" },
  "try.given": { en: "What you are given", zh: "你得到的信息" },
  "try.yes": { en: "Yes", zh: "是" },
  "try.no": { en: "No", zh: "否" },
  "try.another": { en: "Try another question", zh: "再试一题" },
  "try.next": { en: "What happens next", zh: "接下来会发生什么" },
  "try.footer": { en: "Real tasks pay in USDG on Robinhood Chain, straight from the contract.", zh: "真实任务通过 Robinhood Chain 上的 USDG 直接由合约支付。" },
  "try.open": { en: "See open tasks", zh: "查看开放任务" },
  "try.row.answer": { en: "Your answer", zh: "你的回答" },
  "try.row.answer.picked": { en: "You answered “{pick}”.", zh: "你回答了“{pick}”。" },
  "try.row.answer.idle": { en: "Pick Yes or No on the left.", zh: "在左侧选择“是”或“否”。" },
  "try.row.others": { en: "Two other people", zh: "另外两个人" },
  "try.row.others.idle": { en: "They answer the same question on their own.", zh: "他们各自独立回答同一个问题。" },
  "try.row.others.checking": { en: "Comparing your answer with theirs.", zh: "正在将你的回答与他们的比较。" },
  "try.row.others.done": { en: "Both answered “{right}”.", zh: "两人都回答了“{right}”。" },
  "try.row.decision": { en: "Decision", zh: "判定" },
  "try.row.decision.missed": { en: "Your answer did not match. {why}", zh: "你的回答不一致。{why}" },
  "try.row.decision.done": { en: "All three agree. {why}", zh: "三人一致。{why}" },
  "try.row.decision.idle": { en: "Agreement decides whether the answer is accepted.", zh: "一致性决定回答是否被接受。" },
  "try.row.reward": { en: "Reward", zh: "奖励" },
  "try.row.reward.paid": { en: "Released by the contract to your wallet.", zh: "已由合约释放到你的钱包。" },
  "try.row.reward.missed": { en: "No reward this time. It returns to the pool.", zh: "这次没有奖励，资金回到资金池。" },
  "try.row.reward.accepted": { en: "Releasing the reward.", zh: "正在释放奖励。" },
  "try.row.reward.idle": { en: "Paid when the answer is accepted.", zh: "回答被接受后支付。" },

  // Introduction
  "intro.label": { en: "Introduction", zh: "简介" },
  "intro.big": {
    en: "H402 is a board of small pieces of work that need a real person: check a receipt, pick the better option, read a sign, confirm a listing, call a business, go and look. Tasks are posted around the clock with a fixed price. A qualified person does one in minutes. The money is held in escrow and released the moment the work is accepted.",
    zh: "H402 是一个小型工作任务板，这些工作需要真人完成：核对收据、挑选更好的选项、读取标牌、确认房源、给商家打电话、实地查看。任务全天候发布，价格固定。有资格的人几分钟内完成一项。资金托管，工作一经验收即刻释放。",
  },
  "intro.p1": {
    en: "Tasks are posted by the platform and by software connected to it, never by hand, with the price fixed up front. Every task is held in escrow before anyone starts, shown only to people qualified for that type of work, and checked against other answers before anyone is paid.",
    zh: "任务由平台及与之相连的软件发布，从不人工发布，价格事先固定。每个任务在任何人开始之前都已托管，只展示给具备该类工作资格的人，并在付款前与其他回答进行核对。",
  },
  "intro.p2": {
    en: "For the people doing the work it is simple: sign in with a wallet, pass a short qualification, take the tasks you like, and get paid in stablecoins every few minutes. No account, no invoices, no waiting for the end of the month.",
    zh: "对做任务的人来说很简单：用钱包登录，通过简短的资格测试，接你喜欢的任务，每隔几分钟就能收到稳定币报酬。无需账户，无需发票，无需等到月底。",
  },

  // Numbers
  "numbers.label": { en: "H402, live", zh: "H402，实时" },
  "numbers.paid.title": { en: "Rewards paid", zh: "已支付奖励" },
  "numbers.paid.body": { en: "{payments} payments to {people} wallets, every one settled by the contract. ${team} of it came from our own payment tests.", zh: "{payments} 笔支付发给 {people} 个钱包，每一笔都由合约结算。其中 ${team} 来自我们自己的支付测试。" },
  "numbers.paid.fallback": { en: "Every reward is settled by the contract and can be checked on chain.", zh: "每一笔奖励都由合约结算，可在链上查验。" },
  "numbers.paid.link": { en: "See every payment", zh: "查看每一笔支付" },
  "numbers.open.title": { en: "Tasks open right now", zh: "当前开放的任务" },
  "numbers.open.body": { en: "Each one is a fixed reward for one piece of work. Take one, do it, and the reward is yours when it is accepted.", zh: "每个任务都是一项工作的固定奖励。接下它，完成它，验收后奖励就是你的。" },
  "numbers.open.link": { en: "Open the board", zh: "打开任务板" },
  "numbers.waiting.title": { en: "Waiting to be earned", zh: "等待赚取" },
  "numbers.waiting.body": { en: "The total reward on offer across the open tasks. A task's reward is locked in the contract the moment someone takes it.", zh: "所有开放任务提供的奖励总额。有人接下任务的那一刻，奖励就锁定在合约中。" },
  "numbers.waiting.link": { en: "Start earning", zh: "开始赚取" },

  // FAQ
  "faq.label": { en: "FAQs", zh: "常见问题" },
  "faq.title.1": { en: "Frequently Asked", zh: "常见" },
  "faq.title.2": { en: "Questions", zh: "问题" },
  "faq.1.q": { en: "What is H402?", zh: "H402 是什么？" },
  "faq.1.a": { en: "A marketplace for small tasks that need a real person. A client posts a task with a fixed price, a qualified person does it in minutes, and the money is released the moment the work is accepted.", zh: "一个面向需要真人完成的小任务的市场。客户以固定价格发布任务，有资格的人几分钟内完成，工作一经验收，资金即刻释放。" },
  "faq.2.q": { en: "What kind of tasks?", zh: "有哪些类型的任务？" },
  "faq.2.a": { en: "Checking a receipt or a claim, choosing between options, reading a sign or handwriting, labelling items, rating against a short guide, answering a question that needs local knowledge, and action tasks such as filling in a public form or confirming something on a page.", zh: "核对收据或声明、在选项中做选择、读取标牌或手写文字、给物品打标签、按简短指南评分、回答需要本地知识的问题，以及填写公开表单或确认页面内容等行动类任务。" },
  "faq.3.q": { en: "How do I get paid?", zh: "我如何获得报酬？" },
  "faq.3.a": { en: "You sign in with your wallet, and that wallet is where the money goes. Earnings are paid in USDG on Robinhood Chain, in batches every ten minutes, with a transaction link for every payout.", zh: "你用钱包登录，报酬就打到这个钱包。收入以 Robinhood Chain 上的 USDG 支付，每十分钟一批，每笔支付都有交易链接。" },
  "faq.4.q": { en: "When is my work paid?", zh: "我的工作什么时候支付？" },
  "faq.4.a": { en: "When it is accepted. For most tasks that means it agrees with the other people who answered the same task. For action tasks with a written proof the client accepts it, or it is accepted automatically after an hour. Photos and screenshots are looked at by the operator before they are paid.", zh: "在被验收之后。对大多数任务来说，这意味着你的回答与回答同一任务的其他人一致。对提交书面证明的行动类任务，由客户确认，或在一小时后自动接受。照片和截图在支付前由运营人员查看。" },
  "faq.5.q": { en: "What if the client disagrees?", zh: "如果客户不同意怎么办？" },
  "faq.5.a": { en: "A client can dispute within 24 hours. A person on our side looks at both sides and decides. Disputes are rare and never cost you a task you did honestly.", zh: "客户可以在 24 小时内提出异议。我们这边会有人审视双方并做出决定。异议很少见，并且绝不会让你因诚实完成的任务而受损。" },
  "faq.6.q": { en: "Who posts the tasks?", zh: "任务由谁发布？" },
  "faq.6.a": { en: "The platform itself, around the clock, and software systems connected to it. Nobody posts by hand. You never see who asked. They never see who answered.", zh: "由平台本身全天候发布，以及与之相连的软件系统。没有人手动发布。你永远看不到是谁提问，他们也永远看不到是谁回答。" },
  "faq.7.q": { en: "What can a task never ask for?", zh: "任务绝不会要求什么？" },
  "faq.7.a": { en: "Passwords or codes, solving captchas, anything about a private person, buying or sending money on someone's behalf, and sexual or violent content. Tasks like that are refused before they reach you, and you can report anything that slips through.", zh: "密码或验证码、破解验证码、任何关于私人个体的信息、代他人购买或转账，以及色情或暴力内容。此类任务在到达你之前就会被拒绝，漏网的任何任务你都可以举报。" },
  "faq.8.q": { en: "How do I start?", zh: "我如何开始？" },
  "faq.8.a": { en: "Look at the open tasks, connect a wallet, agree to the worker terms, pass a three-question qualification for each type of task you want, and take your first task.", zh: "浏览开放任务，连接钱包，同意工作者条款，为你想做的每类任务通过三道题的资格测试，然后接下你的第一个任务。" },

  // Trust
  "trust.label": { en: "Trust", zh: "信任" },
  "trust.big": {
    en: "The client pays before anyone starts, and no one is paid before the work is accepted. H402 holds every payment in escrow on-chain, checks answers against each other, and refunds whatever was not delivered.",
    zh: "客户在任何人开始之前付款，而在工作被验收之前没有人会获得报酬。H402 将每笔付款托管在链上，相互核对回答，并退还未交付的部分。",
  },
  "trust.p": {
    en: "Workers see only the task, never who asked. Buyers see the answer, the agreement and the transaction, never who answered. Every payout and every refund is a transfer anyone can look up. Trust isn't a promise here: it's the ledger.",
    zh: "做任务的人只看到任务，看不到是谁发布的。买方看到回答、一致性和交易，看不到是谁回答的。每一笔支付和退款都是任何人都能查到的转账。在这里，信任不是承诺，而是账本。",
  },
  "trust.x402": { en: "Payments over the open x402 protocol", zh: "通过开放的 x402 协议支付" },
  "trust.rh": { en: "Rewards in USDG, held by the contract", zh: "以 USDG 支付的奖励，由合约托管" },

  // Footer
  "footer.tagline": { en: "Real people, paid per task.", zh: "真人，按任务付酬。" },
  "footer.open": { en: "Open tasks", zh: "开放任务" },
  "footer.docs": { en: "Docs", zh: "文档" },
  "footer.earn": { en: "Earn", zh: "赚取" },
  "footer.connect": { en: "Connect your software", zh: "接入你的软件" },
  "footer.contact": { en: "Contact", zh: "联系" },
  "footer.privacy": { en: "Privacy Policy", zh: "隐私政策" },
  "footer.terms": { en: "Terms of Use", zh: "使用条款" },

  // First-visit notice
  "notice.title": { en: "Before you start, three things you should know.", zh: "开始之前，有三件事你需要知道。" },
  "notice.1.strong": { en: "Your responses train Otto, our own model.", zh: "你的回答会用于训练我们自己的模型 Otto。" },
  "notice.1.body": { en: " Every answer, note and photo you submit may be used to train Otto, the language model H402 is building from real human work, and to improve the verification systems we and our partners run. Nothing is tied to your name; your wallet address is kept out of training data.", zh: "你提交的每一个回答、备注和照片都可能用于训练 Otto——H402 基于真实人类工作构建的语言模型——并用于改进我们和合作伙伴运行的验证系统。不会与你的姓名关联；你的钱包地址不会进入训练数据。" },
  "notice.2.strong": { en: "Your responses are checked by assistants and by people.", zh: "你的回答会由助手和真人审核。" },
  "notice.2.body": { en: " Responses are reviewed by automated assistants from several providers, including Claude, ChatGPT, Gemini, Grok and DeepSeek, and compared with other people's answers. An operator decides anything the assistants cannot.", zh: "回答会由来自多家提供商的自动助手（包括 Claude、ChatGPT、Gemini、Grok 和 DeepSeek）审核，并与其他人的回答进行比较。助手无法判定的，由运营人员决定。" },
  "notice.3.strong": { en: "Rewards are paid on chain, to your wallet.", zh: "奖励在链上支付到你的钱包。" },
  "notice.3.body": { en: " In USDG on Robinhood Chain, when a response is accepted. Payments cannot be reversed. Tasks are for the United States only.", zh: "回答被接受后，以 Robinhood Chain 上的 USDG 支付。付款不可撤销。任务仅面向美国。" },
  "notice.terms.a": { en: "The full terms are in the ", zh: "完整条款见" },
  "notice.terms.link": { en: "Terms of Use", zh: "使用条款" },
  "notice.terms.and": { en: " and the ", zh: "和" },
  "notice.privacy.link": { en: "Privacy Policy", zh: "隐私政策" },
  "notice.terms.b": { en: ". By continuing you accept them.", zh: "。继续即表示你接受这些条款。" },
  "notice.leave": { en: "Leave", zh: "离开" },
  "notice.accept": { en: "I understand, continue", zh: "我明白了，继续" },

  // 404
  "nf.status": { en: "ERROR 404 / PAGE NOT FOUND", zh: "错误 404 / 页面未找到" },
  "nf.title.a": { en: "This page ", zh: "这个页面" },
  "nf.title.em": { en: "doesn't exist", zh: "不存在" },
  "nf.title.b": { en: ".", zh: "。" },
  "nf.sub": { en: "The task may have closed, or the address may be wrong. Everything that is open right now is on the board.", zh: "任务可能已经关闭，或者地址有误。当前开放的一切都在任务板上。" },
  "nf.cta": { en: "See open tasks", zh: "查看开放任务" },
  "nf.home": { en: "Back home", zh: "返回首页" },
  "nf.docs": { en: "Docs", zh: "文档" },
  "nf.rewards": { en: "Rewards", zh: "奖励" },
  "nf.map": { en: "Map", zh: "地图" },
  "nf.contact": { en: "Contact", zh: "联系" },

  // Types of work
  "type.verify": { en: "Check", zh: "核对" },
  "type.choose": { en: "Choose", zh: "选择" },
  "type.rate": { en: "Rate", zh: "评分" },
  "type.read": { en: "Read", zh: "读取" },
  "type.label": { en: "Label", zh: "标注" },
  "type.answer": { en: "Answer", zh: "回答" },
  "type.do": { en: "Action tasks", zh: "行动任务" },

  // The board
  "board.title": { en: "Open tasks", zh: "开放任务" },
  "board.sub": { en: "Real work, posted around the clock, paid when accepted.", zh: "真实工作，全天候发布，验收后支付。" },
  "board.h1": { en: "H402 tasks", zh: "H402 任务" },
  "board.verified": { en: "Verified", zh: "已认证" },
  "board.badge.us": { en: "United States", zh: "美国" },
  "board.badge.kinds": { en: "{n} kinds of work", zh: "{n} 种工作" },
  "board.badge.new": { en: "New every 5 min", zh: "每 5 分钟更新" },
  "board.badge.fee": { en: "{fee}% service fee", zh: "{fee}% 服务费" },
  "board.stat.lowest": { en: "Lowest price", zh: "最低价格" },
  "board.stat.highest": { en: "Highest price", zh: "最高价格" },
  "board.stat.paid24": { en: "Paid out, 24h", zh: "24 小时支付" },
  "board.stat.paidTotal": { en: "Paid out, total", zh: "累计支付" },
  "board.stat.openNow": { en: "Open now", zh: "当前开放" },
  "board.stat.online": { en: "Workers online", zh: "在线工作者" },
  "board.stat.tasks": { en: "{n} tasks", zh: "{n} 个任务" },
  "board.stat.joined": { en: "{n} joined", zh: "{n} 人加入" },
  "board.tab.tasks": { en: "Tasks", zh: "任务" },
  "board.tab.completed": { en: "Completed", zh: "已完成" },
  "board.tab.activity": { en: "Activity", zh: "动态" },
  "board.tab.how": { en: "How it works", zh: "运作方式" },
  "board.status": { en: "Status", zh: "状态" },
  "board.all": { en: "All", zh: "全部" },
  "board.slots": { en: "Slots open", zh: "有空位" },
  "board.action": { en: "Action tasks", zh: "行动任务" },
  "board.type": { en: "Type of work", zh: "工作类型" },
  "board.price": { en: "Price", zh: "价格" },
  "board.any": { en: "Any", zh: "不限" },
  "board.where": { en: "Where", zh: "地点" },
  "board.anywhere": { en: "Anywhere", zh: "任何地点" },
  "board.remoteOnly": { en: "Remote only", zh: "仅远程" },
  "board.category": { en: "Category", zh: "类别" },
  "board.filters": { en: "Filters", zh: "筛选" },
  "board.search": { en: "Search tasks by title, category or place", zh: "按标题、类别或地点搜索任务" },
  "board.sort.newest": { en: "Recently posted", zh: "最新发布" },
  "board.sort.price_desc": { en: "Price high to low", zh: "价格从高到低" },
  "board.sort.price_asc": { en: "Price low to high", zh: "价格从低到高" },
  "board.sort.ending": { en: "Ending soon", zh: "即将截止" },
  "board.count": { en: "{n} tasks", zh: "{n} 个任务" },
  "board.countOf": { en: "{n} tasks of {total}", zh: "{n} 个任务，共 {total} 个" },
  "board.updated": { en: "Updated live", zh: "实时更新" },
  "board.down": { en: "The board cannot be reached right now. It retries on its own; nothing you have done is lost.", zh: "目前无法连接任务板。它会自动重试；你所做的一切都不会丢失。" },
  "board.empty": { en: "Nothing matches right now. New tasks are posted every few minutes.", zh: "目前没有匹配的任务。每隔几分钟就会发布新任务。" },
  "board.task": { en: "Task", zh: "任务" },
  "board.remote": { en: "Remote", zh: "远程" },
  "board.slotsOf": { en: "{left} of {total} slots", zh: "{left}/{total} 个空位" },
  "board.of": { en: "{left} of {total}", zh: "{left}/{total}" },
  "board.openOf": { en: "{left} of {total} open", zh: "剩余 {left}/{total}" },
  "board.about": { en: "about {n} min", zh: "约 {n} 分钟" },
  "board.pays": { en: "Pays", zh: "报酬" },
  "board.for": { en: "for {name}", zh: "来自 {name}" },
  "board.view": { en: "View and take", zh: "查看并接取" },
  "board.noneCompleted": { en: "Nothing completed yet. Finished tasks show here with the payment that settled them.", zh: "还没有完成的任务。完成的任务会与结算它们的付款一起显示在这里。" },
  "board.paid": { en: "Paid", zh: "已付" },
  "board.each": { en: "{amount} each", zh: "每人 {amount}" },
  "board.agreed": { en: "{pct}% agreed", zh: "{pct}% 一致" },
  "board.onChain": { en: "Payment on chain ↗", zh: "链上付款 ↗" },
  "board.batch": { en: "Paid in a batch", zh: "批量支付" },
  "board.team": { en: "H402 team", zh: "H402 团队" },
  "board.teamTitle": { en: "Done by the H402 team while testing payments. Not counted in the public totals.", zh: "由 H402 团队在测试支付时完成。不计入公开总数。" },
  "board.col.task": { en: "Task", zh: "任务" },
  "board.col.type": { en: "Type", zh: "类型" },
  "board.col.where": { en: "Where", zh: "地点" },
  "board.col.paidPer": { en: "Paid per worker", zh: "每人报酬" },
  "board.col.decidedBy": { en: "Decided by", zh: "判定方式" },
  "board.col.result": { en: "Result", zh: "结果" },
  "board.col.when": { en: "When", zh: "时间" },
  "board.noneActivity": { en: "Nothing completed yet. The first finished tasks will show here.", zh: "还没有完成的任务。最先完成的任务会显示在这里。" },
  "board.accepted": { en: "accepted", zh: "已接受" },
  "board.expired": { en: "expired, refunded", zh: "已过期，已退款" },
  "board.how.1.h": { en: "1. Pick a task", zh: "1. 选一个任务" },
  "board.how.1.b": { en: "Every card is a fixed price for one piece of work: check a receipt, call a store, read a sign, go and look. Sign in with a wallet and pass a three-question qualification for that type of work.", zh: "每张卡片都是一项工作的固定价格：核对收据、给商店打电话、读取标牌、实地查看。用钱包登录，并通过该类工作的三道题资格测试。" },
  "board.how.2.h": { en: "2. Do it, show it", zh: "2. 完成并展示" },
  "board.how.2.b": { en: "Short tasks take seconds. Action tasks come with instructions and a link, and you send back a note, a photo or a screenshot as proof.", zh: "简短任务只需几秒。行动任务附带说明和链接，你需要提交备注、照片或截图作为证明。" },
  "board.how.3.h": { en: "3. Get paid when accepted", zh: "3. 验收后获得报酬" },
  "board.how.3.b": { en: "Short tasks pay when your answer agrees with the others. Action tasks pay when the proof is accepted, or automatically after an hour; photos and screenshots are checked by a person first. Payouts go to your wallet every ten minutes.", zh: "简短任务在你的回答与他人一致时支付。行动任务在证明被接受时支付，或在一小时后自动支付；照片和截图会先由人工检查。报酬每十分钟发放到你的钱包。" },
  "board.live": { en: "Live", zh: "实时" },
  "board.openN": { en: "{n} open", zh: "{n} 个开放" },
  "board.toEarn": { en: "{amount} to be earned", zh: "{amount} 待赚取" },
  "board.onlineN": { en: "{n} online", zh: "{n} 人在线" },
  "board.post": { en: "Post tasks from software", zh: "通过软件发布任务" },
  "board.earn": { en: "Start earning", zh: "开始赚取" },
  "ago.now": { en: "just now", zh: "刚刚" },
  "ago.m": { en: "{n}m ago", zh: "{n} 分钟前" },
  "ago.h": { en: "{n}h ago", zh: "{n} 小时前" },
  "ago.d": { en: "{n}d ago", zh: "{n} 天前" },
};

type T = (key: string, vars?: Record<string, string | number>) => string;

const lookup = (lang: Lang, key: string, vars?: Record<string, string | number>) => {
  const e = STRINGS[key];
  let s = e ? e[lang] || e.en : key;
  if (vars) for (const [n, v] of Object.entries(vars)) s = s.split(`{${n}}`).join(String(v));
  return s;
};

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: T }>({ lang: "en", setLang: () => {}, t: (k, v) => lookup("en", k, v) });

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  // The stored choice is applied after the first paint so the server's English markup matches the first client render.
  useEffect(() => {
    const id = setTimeout(() => {
      try {
        const s = localStorage.getItem(KEY);
        if (s === "zh" || s === "en") setLangState(s);
      } catch {}
    }, 0);
    return () => clearTimeout(id);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }, [lang]);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {}
  }, []);
  const t = useCallback<T>((key, vars) => lookup(lang, key, vars), [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useLang = () => useContext(Ctx);
