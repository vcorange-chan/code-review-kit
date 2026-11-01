(function () {
  var sel = document.getElementById("sel");
  var toast = document.getElementById("toast");
  var lecture = document.body.dataset.lecture;
  var current = null;

  function show(message) {
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(show.timer);
    show.timer = setTimeout(function () { toast.hidden = true; }, 2600);
  }

  function copy(text) {
    var done = function () { show("已复制，粘贴到对话中"); };
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(done, function () { window.prompt("复制这段内容", text); });
    } else {
      window.prompt("复制这段内容", text);
    }
  }

  document.addEventListener("mouseup", function (event) {
    if (sel.contains(event.target)) return;
    setTimeout(function () {
      var selection = window.getSelection();
      var text = selection ? selection.toString().trim() : "";
      var node = selection && selection.anchorNode;
      var element = node && (node.nodeType === 1 ? node : node.parentElement);
      var step = element && element.closest(".step");
      if (!text || !step) { sel.hidden = true; current = null; return; }
      current = { step: step, quote: text.replace(/\s+/g, " ").slice(0, 300) };
      var rect = selection.getRangeAt(0).getBoundingClientRect();
      sel.style.left = Math.max(8, rect.left + window.scrollX) + "px";
      sel.style.top = (rect.bottom + window.scrollY + 6) + "px";
      sel.hidden = false;
    }, 0);
  });

  sel.addEventListener("click", function (event) {
    var kind = event.target.dataset.kind;
    if (!kind || !current) return;
    var step = current.step;
    var quote = current.quote.replace(/"/g, '\\"');
    var target = lecture + "/" + step.dataset.step + ".r" + step.dataset.r;
    if (kind === "chat") {
      copy([
        "讲义：" + document.title,
        "步骤目标：" + step.dataset.goal,
        "源码位置：" + step.dataset.loc,
        "我选中的原文：" + current.quote,
        "我的问题："
      ].join("\n"));
    } else {
      copy("tutor " + kind + " " + target + " \"" + quote + "\" ");
    }
    sel.hidden = true;
  });

  document.querySelectorAll("button.cmd").forEach(function (button) {
    button.addEventListener("click", function () { copy(button.dataset.cmd); });
  });
})();
