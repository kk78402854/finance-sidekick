/* 公共请求、身份、格式化与 UI 小工具 */
(function (global) {
  "use strict";

  const CUSTOMER_KEY = "fa_customer_no";
  const OPERATOR_KEY = "fa_operator_no";

  const identity = {
    get customerNo() {
      return localStorage.getItem(CUSTOMER_KEY) || "";
    },
    setCustomerNo(value) {
      const v = String(value || "").trim();
      if (v) localStorage.setItem(CUSTOMER_KEY, v);
      else localStorage.removeItem(CUSTOMER_KEY);
    },
    get operatorNo() {
      return localStorage.getItem(OPERATOR_KEY) || "";
    },
    setOperatorNo(value) {
      const v = String(value || "").trim();
      if (v) localStorage.setItem(OPERATOR_KEY, v);
      else localStorage.removeItem(OPERATOR_KEY);
    },
  };

  async function request(method, path, { query, body } = {}) {
    const url = new URL(path, global.location.origin);
    if (query) {
      Object.entries(query).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.set(key, value);
        }
      });
    }
    const headers = { "Content-Type": "application/json" };
    if (identity.customerNo) headers["X-Customer-No"] = identity.customerNo;
    if (identity.operatorNo) headers["X-Operator-No"] = identity.operatorNo;

    let resp;
    try {
      resp = await fetch(url.toString(), {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (err) {
      throw new Error("网络请求失败，请确认服务是否在线。");
    }

    let payload = null;
    try {
      payload = await resp.json();
    } catch (err) {
      payload = null;
    }
    if (!resp.ok) {
      const detail = payload && (payload.detail || payload.message);
      throw new Error(detail || `请求失败（HTTP ${resp.status}）`);
    }
    if (payload && payload.code !== undefined && payload.code !== 0) {
      throw new Error(payload.message || "业务处理失败。");
    }
    return payload && payload.data !== undefined ? payload.data : payload;
  }

  const get = (path, query) => request("GET", path, { query });
  const post = (path, body) => request("POST", path, { body });

  // 首次打开页面时补上演示身份，避免每个页面都要求手动输入
  async function ensureIdentity() {
    if (identity.customerNo && identity.operatorNo) return identity;
    try {
      const data = await get("/api/portal/defaults");
      if (!identity.customerNo) identity.setCustomerNo(data.demo_customer_no);
      if (!identity.operatorNo) identity.setOperatorNo(data.operator_no);
    } catch (err) {
      /* 默认值拿不到时保持为空，页面会提示切换身份 */
    }
    return identity;
  }

  function escapeHtml(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmtMoney(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "0.00";
    return num.toLocaleString("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function fmtDate(value) {
    if (!value) return "-";
    return String(value).replace("T", " ").slice(0, 10);
  }

  function fmtDateTime(value) {
    if (!value) return "-";
    return String(value).replace("T", " ").slice(0, 19);
  }

  // 中台的利率字段是小数（0.072 表示 7.2%），统一在前端转成百分数展示
  function fmtRate(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    return `${(num * 100).toFixed(2).replace(/\.?0+$/, "")}%`;
  }

  const labels = {
    accountStatus: {
      normal: "正常",
      active: "正常",
      frozen: "已冻结",
      closed: "已销户",
      dormant: "睡眠户",
    },
    loanStatus: {
      submitted: "待审批",
      processing: "审批中",
      approved: "已通过",
      rejected: "已拒绝",
      cancelled: "已取消",
      disbursed: "已放款",
      expired: "已过期",
    },
    ticketStatus: {
      submitted: "待处理",
      processing: "处理中",
      closed: "已办结",
      approved: "已处理",
      rejected: "已驳回",
    },
    ticketType: {
      complaint: "投诉",
      consult: "咨询",
      suggestion: "建议",
      praise: "表扬",
      card_loss: "信用卡挂失",
      transaction_issue: "交易问题",
      repayment_issue: "还款问题",
      account_issue: "账户问题",
    },
    kycStatus: {
      valid: "有效",
      pending: "待认证",
      expired: "已过期",
      rejected: "未通过",
      none: "未认证",
    },
    complianceStatus: {
      passed: "已通过",
      pending: "待审核",
      failed: "未通过",
    },
    loanType: {
      consumer: "消费贷",
      cash: "现金贷",
      installment: "分期贷",
      business: "经营贷",
    },
    repayment: {
      equal_principal_interest: "等额本息",
      equal_principal: "等额本金",
      interest_first: "先息后本",
    },
    transactionType: {
      transfer: "转账",
      consume: "消费",
      deposit: "存款",
      withdraw: "取现",
      refund: "退款",
      adjustment: "调账",
      wealth_income: "理财收益",
      wealth_purchase: "理财申购",
      wealth_redeem: "理财赎回",
      loan_disbursement: "放款",
      loan_repayment: "还款",
    },
    customerStatus: {
      normal: "正常",
      active: "正常",
      restricted: "受限",
      closed: "已注销",
      cancelled: "已取消",
      blacklisted: "黑名单",
      frozen: "冻结",
    },
  };

  const BADGE_TONE = {
    active: "green", approved: "green", closed: "gray", disbursed: "green",
    normal: "green", success: "green",
    submitted: "amber", processing: "blue", pending: "amber",
    rejected: "red", blacklisted: "red", frozen: "amber", dormant: "gray",
    cancelled: "gray", expired: "gray",
  };

  function badge(status, map, tone) {
    const text = (map && map[status]) || status || "-";
    const cls = tone || BADGE_TONE[status] || "gray";
    return `<span class="badge badge-${cls}">${escapeHtml(text)}</span>`;
  }

  function toast(message, type = "info") {
    let wrap = document.querySelector(".toast-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "toast-wrap";
      document.body.appendChild(wrap);
    }
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = message;
    wrap.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }

  function confirmDialog({ title = "请确认", message = "", okText = "确认", danger = false }) {
    return new Promise((resolve) => {
      const mask = document.createElement("div");
      mask.className = "modal-mask";
      mask.innerHTML = `
        <div class="modal">
          <div class="modal-head">${escapeHtml(title)}</div>
          <div class="modal-body">${message}</div>
          <div class="modal-foot">
            <button class="btn" data-act="cancel">取消</button>
            <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-act="ok">${escapeHtml(okText)}</button>
          </div>
        </div>`;
      const close = (value) => {
        mask.remove();
        resolve(value);
      };
      mask.addEventListener("click", (event) => {
        if (event.target === mask) close(false);
        const act = event.target.getAttribute("data-act");
        if (act === "cancel") close(false);
        if (act === "ok") close(true);
      });
      document.body.appendChild(mask);
    });
  }

  function formDialog({ title = "请填写", message = "", okText = "提交", fields = [] }) {
    return new Promise((resolve) => {
      const mask = document.createElement("div");
      mask.className = "modal-mask";
      const inputs = fields
        .map((field) => {
          const id = "dlg-" + field.name;
          const common = `id="${id}" name="${field.name}" placeholder="${escapeHtml(
            field.placeholder || ""
          )}"`;
          const control =
            field.type === "textarea"
              ? `<textarea ${common} rows="3">${escapeHtml(field.value || "")}</textarea>`
              : `<input type="${field.type || "text"}" ${common} value="${escapeHtml(
                  field.value === undefined || field.value === null ? "" : field.value
                )}" />`;
          return `<div class="field" style="margin-top:12px">
            <label>${escapeHtml(field.label || field.name)}</label>${control}
          </div>`;
        })
        .join("");
      mask.innerHTML = `
        <div class="modal">
          <div class="modal-head">${escapeHtml(title)}</div>
          <div class="modal-body">
            ${message ? `<div>${message}</div>` : ""}
            ${inputs}
          </div>
          <div class="modal-foot">
            <button class="btn" data-act="cancel">取消</button>
            <button class="btn btn-primary" data-act="ok">${escapeHtml(okText)}</button>
          </div>
        </div>`;
      const close = (value) => {
        mask.remove();
        resolve(value);
      };
      mask.addEventListener("click", (event) => {
        if (event.target === mask) close(null);
        const act = event.target.getAttribute("data-act");
        if (act === "cancel") close(null);
        if (act !== "ok") return;
        const values = {};
        for (const field of fields) {
          const el = mask.querySelector(`[name="${field.name}"]`);
          const value = el ? el.value.trim() : "";
          if (field.required && !value) {
            toast(`请填写${field.label || field.name}。`, "error");
            return;
          }
          values[field.name] = value;
        }
        close(values);
      });
      document.body.appendChild(mask);
    });
  }

  function renderPager(container, { pageNo, pageSize, total, onChange }) {
    const totalPages = Math.max(Math.ceil(total / pageSize), 1);
    container.innerHTML = `
      <span>共 ${total} 条 · 第 ${pageNo} / ${totalPages} 页</span>
      <span class="spacer"></span>
      <button class="btn btn-sm" data-page="prev" ${pageNo <= 1 ? "disabled" : ""}>上一页</button>
      <button class="btn btn-sm" data-page="next" ${pageNo >= totalPages ? "disabled" : ""}>下一页</button>`;
    container.querySelectorAll("button[data-page]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const next = btn.dataset.page === "prev" ? pageNo - 1 : pageNo + 1;
        if (next >= 1 && next <= totalPages) onChange(next);
      });
    });
  }

  function showError(container, err) {
    container.innerHTML = `<div class="empty"><strong>加载失败</strong>${escapeHtml(
      err.message || err
    )}</div>`;
  }

  global.FA = {
    identity,
    get,
    post,
    ensureIdentity,
    escapeHtml,
    fmtMoney,
    fmtRate,
    fmtDate,
    fmtDateTime,
    labels,
    badge,
    toast,
    confirmDialog,
    formDialog,
    renderPager,
    showError,
  };
})(window);
