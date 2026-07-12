using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.SceneManagement;

namespace WitnessQA
{
    [Serializable]
    public sealed class WitnessActionEvent : UnityEvent<string, string, int, int> { }

    [Serializable]
    internal sealed class WitnessCommand
    {
        public string id;
        public string kind;
        public string output;
        public string target;
        public string key;
        public int x;
        public int y;
    }

    [Serializable]
    internal sealed class WitnessAck
    {
        public string id;
        public bool ok;
        public string error;
    }

    /// <summary>
    /// Add this component to a bootstrap scene or prefab. Witness writes one atomic command.json
    /// file at a time. Capture requests use Unity's ScreenCapture API; input requests are emitted
    /// as named, opt-in events so the bridge never bypasses the game's own action boundaries.
    /// </summary>
    public sealed class WitnessBridge : MonoBehaviour
    {
        public WitnessActionEvent OnNamedAction = new WitnessActionEvent();
        [Min(0.02f)] public float PollIntervalSeconds = 0.05f;

        private string bridgeDirectory;
        private string commandPath;
        private string ackPath;
        private DateTime lastWriteUtc = DateTime.MinValue;
        private float nextPoll;
        private bool busy;

        private void Awake()
        {
            DontDestroyOnLoad(gameObject);
            bridgeDirectory = Environment.GetEnvironmentVariable("WITNESS_BRIDGE_DIR");
            if (string.IsNullOrWhiteSpace(bridgeDirectory))
            {
                enabled = false;
                return;
            }
            Directory.CreateDirectory(bridgeDirectory);
            commandPath = Path.Combine(bridgeDirectory, "command.json");
            ackPath = Path.Combine(bridgeDirectory, "ack.json");
        }

        private void Update()
        {
            if (!enabled || busy || Time.unscaledTime < nextPoll || !File.Exists(commandPath)) return;
            nextPoll = Time.unscaledTime + PollIntervalSeconds;
            DateTime currentWrite = File.GetLastWriteTimeUtc(commandPath);
            if (currentWrite <= lastWriteUtc) return;
            lastWriteUtc = currentWrite;
            try
            {
                WitnessCommand command = JsonUtility.FromJson<WitnessCommand>(File.ReadAllText(commandPath));
                if (command == null || string.IsNullOrWhiteSpace(command.id)) return;
                if (command.kind == "capture")
                {
                    StartCoroutine(Capture(command));
                    return;
                }
                if (command.kind == "click" || command.kind == "press")
                {
                    OnNamedAction.Invoke(command.target ?? string.Empty, command.key ?? string.Empty, command.x, command.y);
                    WriteAck(command.id, true, string.Empty);
                    return;
                }
                WriteAck(command.id, false, "Unsupported action kind: " + command.kind);
            }
            catch (Exception exception)
            {
                WriteAck("unknown", false, exception.Message);
            }
        }

        private IEnumerator Capture(WitnessCommand command)
        {
            busy = true;
            yield return new WaitForEndOfFrame();
            string output = Path.GetFullPath(command.output);
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            if (File.Exists(output)) File.Delete(output);
            ScreenCapture.CaptureScreenshot(output, 1);
            float deadline = Time.realtimeSinceStartup + 10f;
            while (!File.Exists(output) && Time.realtimeSinceStartup < deadline) yield return null;
            bool created = File.Exists(output);
            WriteAck(command.id, created, created ? string.Empty : "Screenshot was not created before timeout");
            busy = false;
        }

        private void WriteAck(string id, bool ok, string error)
        {
            WitnessAck ack = new WitnessAck { id = id, ok = ok, error = error ?? string.Empty };
            string temporary = ackPath + ".tmp";
            File.WriteAllText(temporary, JsonUtility.ToJson(ack));
            if (File.Exists(ackPath)) File.Delete(ackPath);
            File.Move(temporary, ackPath);
        }
    }
}
