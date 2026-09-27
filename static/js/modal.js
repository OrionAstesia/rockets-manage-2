// 弹窗控制：只做开关，不做 AJAX、不做前端校验（文档 12 第 7.1 节）。
document.addEventListener("DOMContentLoaded", () => {
  // 1) 事件委托：带 data-open-dialog 的按钮打开对应 <dialog>；带 data-close-dialog 的关闭
  document.body.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-open-dialog]");
    if (opener) {
      const dialog = document.getElementById(opener.dataset.openDialog);
      if (dialog) dialog.showModal();
      return;
    }
    const closer = event.target.closest("[data-close-dialog]");
    if (closer) {
      const dialog = closer.closest("dialog");
      if (dialog) dialog.close();
    }
  });

  // 2) 点弹窗外的空白（即 <dialog> 自身区域）关闭
  document.querySelectorAll("dialog.modal").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  // 3) 服务端校验失败后，重新打开被标记的那个弹窗（同一元素只调一次 showModal）
  const toOpen = document.querySelector("dialog[data-open]");
  if (toOpen && !toOpen.open) toOpen.showModal();
});
