using Sandbox;
using System.Collections.Generic;
using System.Threading.Tasks;

public sealed class ClothingPromptTrigger : Component, Component.ITriggerListener
{
    [Property]
    public ClothingPromptUI PromptUI { get; set; }

    [Property]
    public Clothing StandClothing { get; set; }

    [Property]
    public bool RemoveInsteadOfEquip { get; set; }

    [Property]
    public List<Clothing> BaselineClothing { get; set; } = new();

    [Property]
    public bool ResetToBaseline { get; set; }

    private bool _playerInside;
    private bool _isApplying;
    private PlayerController _player;

    public void OnTriggerEnter( Collider other )
    {
        var player = other.GameObject.Components.Get<PlayerController>( FindMode.InAncestors );

        if ( player == null )
            return;

        _player = player;
        _playerInside = true;

        if ( PromptUI != null )
        {
            PromptUI.MyStringValue = ResetToBaseline
                ? "Near a stand — press Use to reset outfit"
                : RemoveInsteadOfEquip
                    ? "Near a stand — press Use to remove"
                    : "Near a stand — press Use to try on";

            PromptUI.ShowPrompt = true;
}
    }

    public void OnTriggerExit( Collider other )
    {
        var player = other.GameObject.Components.Get<PlayerController>( FindMode.InAncestors );

        if ( player == null || player != _player )
            return;

        _playerInside = false;
        _player = null;

        if ( PromptUI != null )
            PromptUI.ShowPrompt = false;
    }

    protected override void OnUpdate()
    {
        if ( !_playerInside )
            return;

        if ( !Input.Pressed( "use" ) )
            return;

        if ( ResetToBaseline && RemoveInsteadOfEquip )
        {
            Log.Warning( "[ClothingPrompt] Choose only one clothing action mode." );
            return;
        }

        if ( ResetToBaseline )
            _ = ResetClothingToBaseline();
        else if ( RemoveInsteadOfEquip )
            _ = RemoveStandClothing();
        else
            _ = EquipStandClothing();
    }

    private async Task EquipStandClothing()
    {
        if ( _isApplying )
            return;

        if ( _player == null )
        {
            Log.Warning( "[ClothingPrompt] Player was not found." );
            return;
        }

        if ( StandClothing == null )
        {
            Log.Warning( "[ClothingPrompt] No clothing asset is assigned to this stand." );
            return;
        }

        var dresser = _player.Components.Get<Dresser>();

        if ( dresser == null )
        {
            Log.Warning( "[ClothingPrompt] Player Controller has no Dresser component." );
            return;
        }

        if ( dresser.Source != Dresser.ClothingSource.Manual )
        {
            Log.Warning( "[ClothingPrompt] Set the player's Dresser Source to Manual." );
            return;
        }

        dresser.Clothing ??= new List<ClothingContainer.ClothingEntry>();

        foreach ( var entry in dresser.Clothing )
        {
            if ( entry.Clothing == StandClothing )
            {
                Log.Info( "[ClothingPrompt] This stand's clothing is already in the Dresser." );
                return;
            }
        }

        for ( int i = dresser.Clothing.Count - 1; i >= 0; i-- )
        {
            var existingClothing = dresser.Clothing[i]?.Clothing;

            if ( existingClothing == null )
                continue;

            if ( StandClothing.CanBeWornWith( existingClothing ) )
                continue;

            dresser.Clothing.RemoveAt( i );
            Log.Info( "[ClothingPrompt] Removed clothing that conflicts with the new item." );
        }
        dresser.Clothing.Add(
            new ClothingContainer.ClothingEntry
            {
                Clothing = StandClothing
            }
        );

        _isApplying = true;

        try
        {
            await dresser.Apply();
            Log.Info( "[ClothingPrompt] Stand clothing applied." );
        }
        catch ( System.Exception exception )
        {
            Log.Error( $"[ClothingPrompt] Failed to apply clothing: {exception}" );
        }
        finally
        {
            _isApplying = false;
        }
    }

    private async Task RemoveStandClothing()
{
    if ( _isApplying )
        return;

    if ( _player == null )
    {
        Log.Warning( "[ClothingPrompt] Player was not found." );
        return;
    }

    if ( StandClothing == null )
    {
        Log.Warning( "[ClothingPrompt] No clothing asset is assigned to this stand." );
        return;
    }

    var dresser = _player.Components.Get<Dresser>();

    if ( dresser == null )
    {
        Log.Warning( "[ClothingPrompt] Player Controller has no Dresser component." );
        return;
    }

    if ( dresser.Source != Dresser.ClothingSource.Manual )
    {
        Log.Warning( "[ClothingPrompt] Set the player's Dresser Source to Manual." );
        return;
    }

    if ( dresser.Clothing == null || dresser.Clothing.Count == 0 )
    {
        Log.Info( "[ClothingPrompt] Stand clothing is not in the Dresser." );
        return;
    }

    bool removed = false;

    for ( int i = dresser.Clothing.Count - 1; i >= 0; i-- )
    {
        if ( dresser.Clothing[i]?.Clothing != StandClothing )
            continue;

        dresser.Clothing.RemoveAt( i );
        removed = true;
    }

    if ( !removed )
    {
        Log.Info( "[ClothingPrompt] Stand clothing is not in the Dresser." );
        return;
    }

    _isApplying = true;

    try
    {
        await dresser.Apply();
        Log.Info( "[ClothingPrompt] Stand clothing removed." );
    }
    catch ( System.Exception exception )
    {
        Log.Error( $"[ClothingPrompt] Failed to remove clothing: {exception}" );
    }
    finally
    {
        _isApplying = false;
    }
}

private async Task ResetClothingToBaseline()
{
    if ( _isApplying )
        return;

    if ( _player == null )
    {
        Log.Warning( "[ClothingPrompt] Player was not found." );
        return;
    }

    var dresser = _player.Components.Get<Dresser>();

    if ( dresser == null )
    {
        Log.Warning( "[ClothingPrompt] Player Controller has no Dresser component." );
        return;
    }

    if ( dresser.Source != Dresser.ClothingSource.Manual )
    {
        Log.Warning( "[ClothingPrompt] Set the player's Dresser Source to Manual." );
        return;
    }

    if ( BaselineClothing == null || BaselineClothing.Count == 0 )
    {
        Log.Warning( "[ClothingPrompt] No baseline outfit is assigned to this stand." );
        return;
    }

    var baselineEntries = new List<ClothingContainer.ClothingEntry>();

    foreach ( var clothing in BaselineClothing )
    {
        if ( clothing == null )
            continue;

        bool alreadyAdded = false;

        foreach ( var entry in baselineEntries )
        {
            if ( entry.Clothing != clothing )
                continue;

            alreadyAdded = true;
            break;
        }

        if ( alreadyAdded )
            continue;

        baselineEntries.Add(
            new ClothingContainer.ClothingEntry
            {
                Clothing = clothing
            }
        );
    }

    if ( baselineEntries.Count == 0 )
    {
        Log.Warning( "[ClothingPrompt] The baseline outfit has no valid clothing items." );
        return;
    }

    dresser.Clothing ??= new List<ClothingContainer.ClothingEntry>();
    dresser.Clothing.Clear();
    dresser.Clothing.AddRange( baselineEntries );

    _isApplying = true;

    try
    {
        await dresser.Apply();
        Log.Info( "[ClothingPrompt] Baseline outfit applied." );
    }
    catch ( System.Exception exception )
    {
        Log.Error( $"[ClothingPrompt] Failed to reset clothing: {exception}" );
    }
    finally
    {
        _isApplying = false;
    }
}
}