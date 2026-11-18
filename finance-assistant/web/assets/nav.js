/* 侧边栏 + 顶栏 + 身份切换，所有页面共用 */
(function (global) {
  "use strict";

  const CUSTOMER_NAV = [
    { key: "profile", label: "我的信息", href: "/customer/profile" },
    { key: "accounts", label: "我的账户", href: "/customer/accounts" },
    { key: "transactions", label: "我的交易", href: "/customer/transactions" },
    { key: "credit-loans", label: "授信与贷款", href: "/customer/credit-loans" },
    { key: "tickets", label: "我的工单", href: "/customer/tickets" },
  ];

  const ADMIN_NAV = [
    { key: "dashboard", label: "数据大盘", href: "/admin/dashboard" },
    { key: "customers", label: "客户管理", href: "/admin/customers" },
    { key: "loan-approvals", label: "贷款审批", href: "/admin/loan-approvals" },
    { key: "tickets", label: "工单处理", href: "/admin/tickets" },
  ];

  function navItem(item, activeKey) {
    const active = item.key === activeKey ? " active" : "";
    return `<a class="nav-item${active}" href="${item.href}">
      <span class="nav-dot"></span>${FA.escapeHtml(item.label)}
    </a>`;
  }

  function renderSidebar(role, activeKey) {
    const items = role === "admin" ? ADMIN_NAV : CUSTOMER_NAV;
    const roleLabel = role === "admin" ? "管理员视角" : "客户视角";
    return `
      <div class="brand">
        <div class="brand-logo">融</div>
        <div>
          <div class="brand-name">金融小二</div>
          <div class="brand-sub">${roleLabel}</div>
        </div>
      </div>
      <div class="nav-group">
        <div class="nav-group-title">业务功能</div>
        ${items.map((item) => navItem(item, activeKey)).join("")}
      </div>
      <div class="nav-group">
        <div class="nav-group-title">通用</div>
        <a class="nav-item" href="/chat"><span class="nav-dot"></span>AI 对话助手</a>
        <a class="nav-item" href="/"><span class="nav-dot"></span>返回首页</a>
      </div>
      <div class="sidebar-foot">
        金融中台 · 演示环境<br>客户与服务数据均来自本地测试库
      </div>`;
  }

  function renderTopbar(role, title, subtitle) {
    const isAdmin = role === "admin";
    const value = isAdmin ? FA.identity.operatorNo : FA.identity.customerNo;
    const label = isAdmin ? "操作员" : "当前客户";
    return `
      <div>
        <div class="topbar-title">${FA.escapeHtml(title || "")}</div>
        <div class="topbar-sub">${FA.escapeHtml(subtitle || "")}</div>
      </div>
      <div class="topbar-spacer"></div>
      <div class="identity">
        <span class="identity-label">${label}</span>
        <input id="identity-input" value="${FA.escapeHtml(value)}"
               placeholder="${isAdmin ? "EMP000001" : "CUS00000001"}"
               autocomplete="off" spellcheck="false">
        <button class="btn btn-sm btn-primary" id="identity-switch">切换</button>
      </div>`;
  }

  function bindSwitch(role) {
    const input = document.getElementById("identity-input");
    const button = document.getElementById("identity-switch");
    if (!input || !button) return;
    const apply = () => {
      const value = input.value.trim().toUpperCase();
      if (!value) {
        FA.toast(role === "admin" ? "请输入员工编号。" : "请输入客户号。", "error");
        return;
      }
      if (role === "admin") FA.identity.setOperatorNo(value);
      else FA.identity.setCustomerNo(value);
      FA.toast("身份已切换，正在刷新数据…", "success");
      global.location.reload();
    };
    button.addEventListener("click", apply);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") apply();
    });
  }

  async function mount() {
    const body = document.body;
    const role = body.dataset.role || "customer";
    const activeKey = body.dataset.page || "";
    const title = body.dataset.title || "";
    const subtitle = body.dataset.subtitle || "";

    await FA.ensureIdentity();

    const sidebar = document.getElementById("sidebar");
    const topbar = document.getElementById("topbar");
    if (sidebar) sidebar.innerHTML = renderSidebar(role, activeKey);
    if (topbar) topbar.innerHTML = renderTopbar(role, title, subtitle);
    bindSwitch(role);

    document.dispatchEvent(new CustomEvent("fa:layout-ready"));
  }

  document.addEventListener("DOMContentLoaded", mount);
})(window);
