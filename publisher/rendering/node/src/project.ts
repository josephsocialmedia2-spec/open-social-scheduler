import {makeProject} from '@revideo/core';
import f1Reel from './scenes/f1-reel.js';

export default makeProject({
  name: 'f1-renderer-v2',
  scenes: [f1Reel],
  settings: {
    shared: {
      background: '#07100A',
      range: [0, Infinity],
      size: {x: 1080, y: 1920},
    },
    preview: {
      fps: 30,
      resolutionScale: 1,
    },
    rendering: {
      exporter: {
        name: '@revideo/core/wasm',
      },
      fps: 30,
      resolutionScale: 1,
      colorSpace: 'srgb',
    },
  },
});
