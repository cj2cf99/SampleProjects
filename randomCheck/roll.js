const RangeDice = (() => {
  const minimum = 3;
  const maximum = 30;
  const maxFaces = 8;
  const wordSpace = 2 ** 32;
  const randomWord = new Uint32Array(1);

  function validBound(value) {
    return Number.isInteger(value) && value >= minimum && value <= maximum;
  }

  function validBounds(lower, upper) {
    return validBound(lower) && validBound(upper) && lower <= upper;
  }

  function plan(upper) {
    const count = Math.ceil(upper / maxFaces);
    // Start from D4s, then add pairs of faces to reach the smallest usable capacity.
    const extraPairs = Math.max(0, Math.ceil(upper / 2) - count * 2);
    const eights = Math.floor(extraPairs / 2);
    const sixes = extraPairs % 2;
    return [
      ...Array(count - eights - sixes).fill(4),
      ...Array(sixes).fill(6),
      ...Array(eights).fill(8),
    ];
  }

  function uniform(limit) {
    if (limit === 1) return 0;
    const cutoff = wordSpace - wordSpace % limit;
    do {
      crypto.getRandomValues(randomWord);
    } while (randomWord[0] >= cutoff);
    return randomWord[0] % limit;
  }

  function roll(lower, upper) {
    // Draw the total first so every possible sum has the same chance.
    const score = lower + uniform(upper - lower + 1);
    const ending = uniform(2) === 0 ? 'forward' : 'back';
    const faces = plan(upper).slice(0, score);
    let remaining = score;
    let capacityAhead = faces.reduce((sum, sides) => sum + sides, 0);
    const dice = faces.map((sides, i) => {
      capacityAhead -= sides;
      const minimumHere = Math.max(1, remaining - capacityAhead);
      const maximumHere = Math.min(sides, remaining - (faces.length - i - 1));
      const value = minimumHere + uniform(maximumHere - minimumHere + 1);
      remaining -= value;
      return { sides, value };
    });
    dice.at(-1).ending = ending;
    return { score, dice };
  }

  return { validBound, validBounds, plan, roll };
})();

if (typeof document !== 'undefined') {
  const form = document.querySelector('#roll-form');
  const lowerInput = document.querySelector('#lower');
  const upperInput = document.querySelector('#upper');
  const button = document.querySelector('#roll-button');
  const buttonLabel = document.querySelector('#button-label');
  const inputError = document.querySelector('#input-error');
  const receipt = document.querySelector('#receipt');
  const result = document.querySelector('#result');
  const calculation = document.querySelector('#calculation');
  const rangeSummary = document.querySelector('#range-summary');
  const playArea = document.querySelector('#play-area');
  const stage = document.querySelector('#dice-stage');
  const stageState = document.querySelector('#stage-state');
  const diceLabel = document.querySelector('#dice-labels');
  const modePicker = document.querySelector('#mode-picker');
  const renderer = DiceMotion.createStage(document.querySelector('#dice-canvas'));
  const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
  let rolling = false;

  function displayDice(dice, reveal = false) {
    diceLabel.replaceChildren(...dice.map(die => {
      const token = document.createElement('span');
      token.className = 'face-token';
      token.textContent = `D${die.sides}`;
      if (reveal) {
        const value = document.createElement('b');
        value.textContent = ` · ${die.value}`;
        token.append(value);
      }
      return token;
    }));
  }

  function updateMode() {
    const flat = modePicker.querySelector('input:checked').value === 'flat';
    stage.classList.toggle('flat', flat);
    stage.classList.toggle('solid', !flat);
    stage.setAttribute('aria-label', flat ? '2D 卡通骰' : '3D 镜面骰');
    renderer.setFlat(flat);
  }

  function displayReady() {
    const lower = lowerInput.valueAsNumber, upper = upperInput.valueAsNumber;
    if (!RangeDice.validBounds(lower, upper)) return;
    const dice = DiceMotion.placeDice(RangeDice.plan(upper).map(sides => ({ sides, value: null })));
    result.value = '–';
    receipt.classList.remove('is-revealed');
    calculation.textContent = '设定范围后，点击「掷骰子」。';
    rangeSummary.textContent = `${lower} – ${upper}`;
    displayDice(dice);
    stageState.textContent = '待投掷';
    renderer.render(dice, null);
  }

  function describe({ score, dice }) {
    if (dice.length === 1) return `骰面点数 ${score}`;
    return `${dice.map(die => die.value).join(' + ')} = ${score}`;
  }

  function setRolling(value) {
    rolling = value;
    playArea.classList.toggle('is-rolling', value);
    button.disabled = lowerInput.disabled = upperInput.disabled = value;
    buttonLabel.textContent = value ? '翻滚中' : '掷骰子';
  }

  form.noValidate = true;
  modePicker.addEventListener('change', updateMode);
  form.addEventListener('input', () => {
    inputError.hidden = true;
    lowerInput.removeAttribute('aria-invalid');
    upperInput.removeAttribute('aria-invalid');
    displayReady();
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (rolling) return;
    const lower = lowerInput.valueAsNumber;
    const upper = upperInput.valueAsNumber;
    if (!RangeDice.validBounds(lower, upper)) {
      inputError.textContent = '请输入 3–30 之间的整数，最小值不能大于最大值。';
      inputError.hidden = false;
      const invalid = RangeDice.validBound(lower) ? upperInput : lowerInput;
      invalid.setAttribute('aria-invalid', 'true');
      invalid.focus();
      return;
    }
    inputError.hidden = true;
    let outcome;
    try {
      outcome = RangeDice.roll(lower, upper);
    } catch {
      inputError.textContent = '网页随机数暂时不可用，请重试。';
      inputError.hidden = false;
      return;
    }
    const dice = DiceMotion.placeDice(outcome.dice, true);
    const restoreFocus = document.activeElement === button;
    setRolling(true);
    receipt.classList.remove('is-revealed');
    result.value = '–';
    calculation.textContent = '骰子翻滚中…';
    stageState.textContent = '翻滚中';
    displayDice(dice);
    const reduced = motionPreference.matches;
    const duration = DiceMotion.duration(reduced, dice.length);
    const start = performance.now();

    function frame(now) {
      const elapsed = now - start;
      if (elapsed < duration) {
        renderer.render(dice, elapsed, reduced);
        requestAnimationFrame(frame);
        return;
      }
      renderer.render(dice, null, reduced);
      displayDice(dice, true);
      stageState.textContent = '已落定';
      result.value = String(outcome.score);
      calculation.textContent = describe(outcome);
      receipt.classList.add('is-revealed');
      setRolling(false);
      if (restoreFocus && document.activeElement === document.body) button.focus({preventScroll: true});
    }

    requestAnimationFrame(frame);
  });

  updateMode();
  displayReady();
}
