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
      var text = selection ? selection.toString() : "";
      var node = selection && selection.anchorNode;
      var element = node && (node.nodeType === 1 ? node : node.parentElement);
      var step = element && element.closest(".step");
      var endNode = selection && selection.focusNode;
      var endElement = endNode && (endNode.nodeType === 1 ? endNode : endNode.parentElement);
      var revision = element && element.closest("[data-revision]");
      if (!text.trim() || !step || !endElement || endElement.closest(".step") !== step || endElement.closest("[data-revision]") !== revision) {
        sel.hidden = true; current = null; return;
      }
      current = { step: step, revision: revision.dataset.revision, goal: revision.dataset.goal || step.dataset.goal, quote: text };
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
    var target = lecture + "/" + step.dataset.step + ".r" + current.revision;
    if (kind === "chat") {
      copy([
        "讲义：" + document.title,
        "步骤目标：" + current.goal,
        "源码位置：" + step.dataset.loc,
        "我选中的原文：" + current.quote,
        "我的问题："
      ].join("\n"));
    } else {
      copy("tutor " + kind + " " + JSON.stringify({target: target, quote: current.quote}) + " ");
    }
    sel.hidden = true;
  });

  document.querySelectorAll("button.cmd").forEach(function (button) {
    button.addEventListener("click", function () { copy(button.dataset.cmd); });
  });
})();
