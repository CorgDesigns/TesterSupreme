using Sandbox;

public sealed class ClothingZoneDebug : Component, Component.ITriggerListener
{
    public void OnTriggerEnter(Collider other)
    {
        var playerController = other.GameObject.Components.Get<PlayerController>(FindMode.InAncestors);

        if (!playerController.IsValid())
        {
            Log.Info($"[ClothingZone] Ignored non-player collider: {other.GameObject.Name}");
            return;
        }

        Log.Info($"[ClothingZone] Player entered: {playerController.GameObject.Name}; collider: {other.GameObject.Name}");
    }

    public void OnTriggerExit(Collider other)
    {
        var playerController = other.GameObject.Components.Get<PlayerController>(FindMode.InAncestors);

        if (!playerController.IsValid())
        {
            Log.Info($"[ClothingZone] Ignored non-player collider: {other.GameObject.Name}");
            return;
        }

        Log.Info($"[ClothingZone] Player exited: {playerController.GameObject.Name}; collider: {other.GameObject.Name}");
    }
}