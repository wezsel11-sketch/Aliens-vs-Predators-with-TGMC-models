version "4.0"

// Every 20 to 45 seconds, each player hears a distant xeno noise (a roar, something crawling in the vents,
// an egg moving), not tied to a place, at a random low volume. Registered by hive_ambience.mapinfo.
class HiveAmbience : EventHandler
{
	int countdown;

	override void WorldLoaded(WorldEvent e)
	{
		countdown = 35 * random(10, 25);
	}

	override void WorldTick()
	{
		if (--countdown > 0) return;
		countdown = 35 * random(20, 45);
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (playeringame[i] && players[i].mo)
				players[i].mo.A_StartSound("hive/ambient", CHAN_7, CHANF_LOCAL | CHANF_NOSTOP, frandom(0.3, 0.6), ATTN_NONE);
		}
	}
}
